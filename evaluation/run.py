"""Reproducible evaluation for ScholarScope AI.

Run from the project root:
    backend/.venv/Scripts/python -m evaluation.run            # offline experiments E1-E5 (+ E7 from the live DB)
    backend/.venv/Scripts/python -m evaluation.run --llm      # also E6 (calls the configured LLM; costs tokens)

Writes evaluation/results/latest.json (read by the admin Evaluation page) and evaluation/results/report.md.
All inputs are archived snapshots or labelled files in evaluation/; nothing depends on websites being online.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
BACKEND = PROJECT / "backend"
TMP = Path(tempfile.mkdtemp(prefix="scholarscope-eval-"))
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
(TMP / "data" / "fixtures").mkdir(parents=True)
(TMP / "data" / "snapshots").mkdir(parents=True)
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import Candidate, ChangeEvent, CrawlJob, Scholarship, Source  # noqa: E402
from app.services import trust  # noqa: E402
from app.services.connectors.nsp_listing import parse_nsp_listing  # noqa: E402
from app.services.crawl import orchestrator  # noqa: E402
from app.services.extraction.text import text_hash  # noqa: E402
from app.services.ingestion.csv_import import import_dataset, read_csv_bytes  # noqa: E402
from app.services.matching import rank_matches, name_similarity  # noqa: E402
from app.services.normalize import normalize_dataset_row  # noqa: E402
from app.services.recommendation import eligibility as E  # noqa: E402
from app.services.sources.fetcher import SafeFetcher  # noqa: E402
from evaluation.baselines import legacy_v1  # noqa: E402

TODAY = date(2026, 10, 18)  # date of the archived snapshots
DATASET = BACKEND / "data" / "imports" / "india_scholarship_dataset_2026_27_researched.csv"
SNAPSHOT = ROOT / "snapshots" / "nsp_all_scholarships_2026-10-18.html"
REAL_HTML = SNAPSHOT.read_text(encoding="utf-8")
ROW = '<div class="row mb-4 border-1 border-bottom">'


def gold(name: str) -> dict:
    return json.loads((ROOT / "gold" / name).read_text(encoding="utf-8"))


def ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def find_key(title: str, keys) -> str | None:
    t = ws(title)
    hits = [k for k in keys if ws(k) in t]
    return max(hits, key=len) if hits else None


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return p, r, f


def r3(x):
    return None if x is None else round(x, 3)


# --------------------------------------------------------------------------- pipeline harness

class Harness:
    """Fresh in-memory database with the dataset imported and an NSP-listing fixture source."""

    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.db = self.Session()
        import_dataset(self.db, DATASET.read_bytes(), file_name=DATASET.name, version="eval", dataset_name="eval")
        self.src = Source(key="eval_nsp", name="Archived NSP listing (fixture)", classification="official",
                          base_url="fixture://", target_urls=["fixture://nsp.html"], allowed_url_patterns=["fixture://*"],
                          connector="nsp_listing")
        self.db.add(self.src)
        self.db.commit()

    def run(self, html: str) -> CrawlJob:
        (TMP / "data" / "fixtures" / "nsp.html").write_text(html, encoding="utf-8")
        job = orchestrator.enqueue(self.db, self.src, "cli")
        orchestrator.run_job(job.id, self.Session, SafeFetcher(sleep=lambda s: None))
        self.db.expire_all()
        return self.db.get(CrawlJob, job.id)

    def events_since(self, job: CrawlJob) -> list[ChangeEvent]:
        return list(self.db.scalars(select(ChangeEvent).where(ChangeEvent.job_id == job.id)))

    def ext(self, sid: str) -> str:
        return self.db.get(Scholarship, sid).external_id


def make_student(**kw):
    """A persona with every profile attribute present (missing ones are None = unknown)."""
    from types import SimpleNamespace

    base = dict(education_level=None, current_class=None, year_of_study=None, course_name=None, discipline=None,
                qualifying_exam_percentage=None, cgpa=None, cgpa_scale=10.0, annual_family_income=None, state=None,
                gender=None, category=None, has_disability=None, disability_percent=None, is_indian_citizen=None,
                special_circumstances=[], special_circumstances_none=False)
    base.update(kw)
    return SimpleNamespace(**base)


def dataset_rows() -> list[dict]:
    return read_csv_bytes(DATASET.read_bytes())


# --------------------------------------------------------------------------- E1 parser

def perturb_whitespace(html: str) -> str:
    return re.sub(r">\s+<", ">\n   \n<", html).replace("  ", " \n ")


def perturb_class_order(html: str) -> str:
    return html.replace(ROW, '<div class="border-bottom mb-4 row border-1 extra-class">')


def perturb_wrapper(html: str) -> str:
    return html.replace(ROW, f'<section class="wrap">{ROW}').replace('<div class="col-md-2">', '<div class="col-md-2">', 1)


def e1_parser() -> dict:
    g = gold("nsp_listing_fields.json")
    variants = {"archived page (real)": REAL_HTML, "whitespace reformatted (synthetic)": perturb_whitespace(REAL_HTML),
                "class order changed (synthetic)": perturb_class_order(REAL_HTML),
                "extra wrapper elements (synthetic)": perturb_wrapper(REAL_HTML)}
    metrics, details = [], {}
    for label, html in variants.items():
        schemes = parse_nsp_listing(html)
        correct = total = 0
        errors = []
        for s in schemes:
            exp = {**g["default"], **g["overrides"].get(find_key(s.title, g["overrides"]) or "", {})}
            for f in ("open_date", "deadline", "renewal_only"):
                got = getattr(s, f)
                got = got.isoformat() if isinstance(got, date) else got
                total += 1
                if got == exp[f]:
                    correct += 1
                else:
                    errors.append(f"{s.title[:50]}: {f} {got} != {exp[f]}")
        details[label] = errors[:10]
        metrics.append({"name": f"{label}: schemes parsed", "value": len(schemes), "note": f"expected {g['expected_scheme_count']}"})
        metrics.append({"name": f"{label}: field accuracy (open date, deadline, renewal flag)",
                        "value": r3(correct / total) if total else None, "n": total})
    return {"id": "E1", "title": "NSP listing parser accuracy",
            "description": "Deterministic parser vs. labelled values for every scheme row, on the real archived page and on synthetic markup perturbations.",
            "data": "snapshots/nsp_all_scholarships_2026-10-18.html; gold/nsp_listing_fields.json",
            "metrics": metrics, "errors": details,
            "limitations": ["Single real snapshot; real future layout changes may differ from the synthetic perturbations.",
                            "Gold labels were read by the developer from the same page; perfect scores mainly show the parser is faithful, not that it generalises."]}


# --------------------------------------------------------------------------- E2 entity resolution

def e2_entity_resolution() -> dict:
    g = gold("entity_resolution.json")["mapping"]
    recs = []
    for row in dataset_rows():
        f, _ = normalize_dataset_row(row)
        recs.append(type("R", (), {"id": f["external_id"], "name": f["name"], "official_source_url": f["official_source_url"],
                                   "application_url": f["application_url"], "provider": f["provider"]})())
    schemes = parse_nsp_listing(REAL_HTML)

    def evaluate(decide) -> dict:
        tp = fp = fn = deferred = wrong = 0
        for s in schemes:
            truth = g[find_key(s.title, g)]
            decision, rid = decide(s)
            if decision == "auto":
                if rid == truth:
                    tp += 1
                else:
                    fp += 1
                    wrong += 1
                    if truth != "NEW":
                        fn += 1
            elif decision == "possible":
                deferred += 1
                if truth != "NEW":
                    fn += 1
            elif truth != "NEW":
                fn += 1
        p, r, f = prf(tp, fp, fn)
        return {"precision": p, "recall": r, "f1": f, "wrong_merges": wrong, "deferred": deferred, "tp": tp}

    def proposed(s):
        m = rank_matches(s.title, s.guideline_url, s.ministry, recs)
        return (m[0].decision, m[0].record_id) if m else ("none", None)

    def no_discriminators(s):
        best = max(recs, key=lambda r: name_similarity(s.title, r.name))
        return ("auto" if name_similarity(s.title, best.name) >= 0.86 else "none"), best.id

    def exact_name(s):
        from app.services.normalize import normalize_name
        hit = next((r for r in recs if normalize_name(r.name) == normalize_name(s.title)), None)
        return ("auto", hit.id) if hit else ("none", None)

    res = {k: evaluate(fn) for k, fn in (("proposed", proposed), ("similarity_only", no_discriminators), ("exact_name", exact_name))}
    names = {"precision": "Auto-match precision", "recall": "Auto-match recall", "f1": "Auto-match F1",
             "wrong_merges": "Wrong automatic merges", "deferred": "Sent to human review"}
    metrics = [{"name": names[k], "value": r3(res["proposed"][k]) if isinstance(res["proposed"][k], float) else res["proposed"][k],
                "n": len(schemes)} for k in names]
    baseline = [{"name": names[k], "value": r3(res["similarity_only"][k]) if isinstance(res["similarity_only"][k], float) else res["similarity_only"][k]} for k in names]
    return {"id": "E2", "title": "Entity resolution / duplicate detection",
            "description": "Linking NSP listing schemes to dataset records. Baseline = name similarity alone (same 0.86 threshold, no discriminator words, no URL/provider signals). An exact-normalized-name baseline is in extra.",
            "data": "31 schemes on the archived NSP page; gold/entity_resolution.json (28 schemes present in the dataset, 3 absent)",
            "metrics": metrics, "baseline": baseline,
            "extra": {"exact_name": {k: r3(v) if isinstance(v, float) else v for k, v in res["exact_name"].items()}},
            "limitations": ["Small n (31). Precision is prioritised over recall by design: uncertain pairs go to review."]}


# --------------------------------------------------------------------------- E3 change detection

def _row_bounds(html: str, title: str) -> tuple[int, int]:
    at = html.index(title)
    end = html.find(ROW, at)
    return html.rindex(ROW, 0, at), end if end > 0 else html.index("</div>", at)


def _edit_row(html: str, title: str, old: str, new: str) -> str:
    a, b = _row_bounds(html, title)
    seg = html[a:b]
    assert old in seg, f"{old} not in row {title}"
    return html[:a] + seg.replace(old, new) + html[b:]


def _drop_row(html: str, title: str) -> str:
    a, b = _row_bounds(html, title)
    return html[:a] + html[b:]


def revisions() -> list[dict]:
    h = REAL_HTML
    new_row = (f'{ROW}<div class="col-md-10"><h6>Example Fixture Scholarship For Testing (Merit Based Scheme)</h6>'
               '<span>Scheme Open from : 01-10-2026</span><span>Student Application Open till : 30-11-2026</span></div></div>')
    first_row = h.index(ROW, h.index("collapseOne14"))
    return [
        {"id": "R1", "kind": "cosmetic", "desc": "whitespace / line breaks reformatted", "html": perturb_whitespace(h), "gold": []},
        {"id": "R2", "kind": "cosmetic", "desc": "page chrome text changed (title, nav)", "html": h.replace("NSP : National Scholarship Portal", "NSP | National Scholarship Portal 2.0").replace("Students</button>", "Students (new)</button>"), "gold": []},
        {"id": "R3", "kind": "cosmetic", "desc": "scheme name re-capitalised", "html": h.replace("Prime Minister'S Scholarship Scheme For Ministry Of Railways", "PRIME MINISTER'S SCHOLARSHIP SCHEME FOR MINISTRY OF RAILWAYS"), "gold": []},
        {"id": "R4", "kind": "material", "desc": "one deadline extended", "html": _edit_row(h, "Girl Students ( Technical Degree)", "31-10-2026", "15-11-2026"), "gold": [("IND-NSP-003", "deadline")]},
        {"id": "R5", "kind": "material", "desc": "opening date changed", "html": _edit_row(h, "For Higher Professional", "15-07-2026", "20-07-2026"), "gold": [("IND-NSP-015", "open_date")]},
        {"id": "R6", "kind": "material", "desc": "scheme removed from listing", "html": _drop_row(h, "National Renewable Energy Fellowship Scheme"), "gold": [("IND-NSP-016", "listing_presence")]},
        {"id": "R7", "kind": "material", "desc": "two deadlines changed", "html": _edit_row(_edit_row(h, "Swanath Scholarship Scheme ( Technical Degree)", "31-10-2026", "30-11-2026"), "(Nts-Ug)", "31-10-2026", "07-11-2026"), "gold": [("IND-NSP-001", "deadline"), ("IND-NSP-017", "deadline")]},
        {"id": "R8", "kind": "material", "desc": "window becomes renewal-only", "html": _edit_row(_edit_row(h, "Ministry Of Railways", "Open from :", "Open from (for Renewal):"), "Ministry Of Railways", "Open till :", "Open till (for Renewal):"), "gold": [("IND-NSP-022", "renewal_type")]},
        {"id": "R9", "kind": "material", "desc": "reformatted page + one deadline change", "html": perturb_whitespace(_edit_row(h, "(CSSS)", "31-10-2026", "10-11-2026")), "gold": [("IND-NSP-014", "deadline")]},
        {"id": "R10", "kind": "discovery", "desc": "new scheme row added (synthetic scheme)", "html": h[:first_row] + new_row + h[first_row:], "gold": [], "expect_new_candidate": 1},
    ]


def e3_change_detection() -> dict:
    tp = fp = fn = 0
    rev_rows, cosmetic_false_alarms, rev_flags, baseline_flags = [], 0, [], []
    discovery_ok = None
    for rv in revisions():
        h = Harness()
        j0 = h.run(REAL_HTML)
        cand_before = h.db.query(Candidate).count()
        j = h.run(rv["html"])
        evs = [e for e in h.events_since(j) if e.materiality == "material" and e.scholarship_id]
        detected = {(h.ext(e.scholarship_id), e.field) for e in evs}
        g = set(rv["gold"])
        tp += len(detected & g)
        fp += len(detected - g)
        fn += len(g - detected)
        flagged = bool(detected)
        rev_flags.append((rv["kind"] == "material", flagged))
        baseline_flags.append((rv["kind"] == "material", rv["html"] != REAL_HTML))
        if rv["kind"] == "cosmetic" and flagged:
            cosmetic_false_alarms += 1
        if rv["id"] == "R10":
            discovery_ok = h.db.query(Candidate).count() - cand_before
        rev_rows.append({"revision": rv["id"], "kind": rv["kind"], "desc": rv["desc"], "status": j.status,
                         "detected": sorted(detected), "expected": sorted(g),
                         "auto_accepted": sum(1 for e in evs if e.review_status == "auto_accepted")})
        assert j0.status == "succeeded"
    p, r, f = prf(tp, fp, fn)

    def rev_prf(flags):
        t = sum(1 for m, fl in flags if m and fl)
        fpos = sum(1 for m, fl in flags if not m and fl)
        fneg = sum(1 for m, fl in flags if m and not fl)
        return prf(t, fpos, fneg)

    rp, rr, rf = rev_prf(rev_flags)
    bp, br, bf = rev_prf(baseline_flags)

    # HTML page monitor: cosmetic filtering (synthetic page variants, labelled)
    base = "<main><h1>Post-matric scholarship</h1><p>Family income up to Rs. 2.5 lakh per year.</p><p>" + "Eligibility text. " * 15 + "</p></main>"
    pages = [
        ("nav menu changed", "<nav>Home | About | NEW</nav>" + base, False),
        ("footer 'last updated' changed", base + "<footer>Last updated: 9 Oct 2026</footer>", False),
        ("visitor counter changed", base.replace("</main>", "<p>Visitors: 120934</p></main>"), False),
        ("copyright year changed", base + "<p>© 2027</p>", False),
        ("income limit changed", base.replace("2.5 lakh", "3 lakh"), True),
        ("closure statement added", base.replace("</main>", "<p>Applications are now closed.</p></main>"), True),
    ]
    from app.services.extraction.text import html_to_text

    reference = "<nav>Home | About</nav>" + base + "<footer>Last updated: 1 Oct 2026</footer><p>Visitors: 120001</p><p>© 2026</p>"
    ref_hash = text_hash(html_to_text(reference).text)
    pm_flags, pm_base = [], []
    for _desc, html, material in pages:
        variant = reference
        if "NEW" in html:
            variant = reference.replace("About</nav>", "About | NEW</nav>")
        elif "9 Oct" in html:
            variant = reference.replace("1 Oct 2026", "9 Oct 2026")
        elif "120934" in html:
            variant = reference.replace("120001", "120934")
        elif "© 2027" in html:
            variant = reference.replace("© 2026", "© 2027")
        elif "3 lakh" in html:
            variant = reference.replace("2.5 lakh", "3 lakh")
        else:
            variant = reference.replace("</main>", "<p>Applications are now closed.</p></main>")
        pm_flags.append((material, text_hash(html_to_text(variant).text) != ref_hash))
        pm_base.append((material, variant != reference))
    pp, pr, pf = rev_prf(pm_flags)
    pbp, pbr, pbf = rev_prf(pm_base)

    metrics = [
        {"name": "Field-level change precision", "value": r3(p), "n": tp + fp, "note": "detected (scheme, field) pairs"},
        {"name": "Field-level change recall", "value": r3(r), "n": tp + fn},
        {"name": "Field-level change F1", "value": r3(f)},
        {"name": "Revision-level alert precision (listing)", "value": r3(rp), "n": len(rev_flags)},
        {"name": "Revision-level alert recall (listing)", "value": r3(rr)},
        {"name": "Cosmetic revisions raising a material alert", "value": cosmetic_false_alarms, "n": 3},
        {"name": "New scheme candidates created for R10", "value": discovery_ok, "note": "expected 1"},
        {"name": "Page monitor: material-change precision", "value": r3(pp), "n": len(pm_flags)},
        {"name": "Page monitor: material-change recall", "value": r3(pr)},
    ]
    baseline = [
        {"name": "Field-level change precision", "value": "not supported"},
        {"name": "Field-level change recall", "value": "not supported"},
        {"name": "Field-level change F1", "value": "not supported"},
        {"name": "Revision-level alert precision (listing)", "value": r3(bp)},
        {"name": "Revision-level alert recall (listing)", "value": r3(br)},
        {"name": "Cosmetic revisions raising a material alert", "value": sum(1 for rv in revisions() if rv["kind"] == "cosmetic" and rv["html"] != REAL_HTML)},
        {"name": "New scheme candidates created for R10", "value": "not supported"},
        {"name": "Page monitor: material-change precision", "value": r3(pbp)},
        {"name": "Page monitor: material-change recall", "value": r3(pbr)},
    ]
    return {"id": "E3", "title": "Change detection: material vs cosmetic",
            "description": "10 labelled revisions of the real NSP page (3 cosmetic, 6 material, 1 new scheme) run through the full pipeline from a fresh database each time, plus 6 labelled HTML page variants for the generic page monitor. Baseline = whole-page byte-hash comparison.",
            "data": "Synthetic revisions derived from snapshots/nsp_all_scholarships_2026-10-18.html (defined in evaluation/run.py)",
            "metrics": metrics, "baseline": baseline, "revisions": rev_rows,
            "limitations": ["Revisions are synthetic edits of a real page; they test the mechanism, not the real-world rate of changes.",
                            "Byte-hash baseline cannot localise which field changed, so field-level metrics do not apply to it."]}


# --------------------------------------------------------------------------- E4 eligibility

def e4_eligibility() -> dict:
    g = gold("eligibility_cases.json")
    rows = {r["scholarship_id"]: r for r in dataset_rows()}
    from types import SimpleNamespace

    def to_label(outcome: str) -> str:
        return {"eligible": "eligible", "not_eligible": "not_eligible"}.get(outcome, "undetermined")

    table, preds = [], {"proposed": [], "legacy_v1": [], "unknown_as_satisfied": []}
    for c in g["cases"]:
        persona = g["personas"][c["persona"]]
        st = make_student(**persona)
        fields, _ = normalize_dataset_row(rows[c["scholarship"]])
        s = SimpleNamespace(**fields)
        crit = E.evaluate(st, s, {})
        prop = to_label(E.outcome(crit))
        ablation = "not_eligible" if any(x["status"] == E.NOT_SATISFIED for x in crit) else "eligible"
        leg = legacy_v1.check_eligibility(legacy_v1.legacy_student(persona), legacy_v1.legacy_scholarship(rows[c["scholarship"]]))
        legacy = "eligible" if leg["is_eligible"] else "not_eligible"
        for k, v in (("proposed", prop), ("legacy_v1", legacy), ("unknown_as_satisfied", ablation)):
            preds[k].append((c["expected"], v))
        table.append({"persona": c["persona"], "scholarship": c["scholarship"], "expected": c["expected"],
                      "proposed": prop, "legacy_v1": legacy, "unknown_as_satisfied": ablation,
                      "unknown_reasons": sorted({x["unknown_reason"] for x in crit if x["status"] == E.UNKNOWN}),
                      "first_failed": next((x["label"] for x in crit if x["status"] == E.NOT_SATISFIED), None)})

    def score(pairs):
        n = len(pairs)
        acc = sum(1 for e, p in pairs if e == p) / n
        neg = [(e, p) for e, p in pairs if e != "eligible"]
        fpr = sum(1 for e, p in neg if p == "eligible") / len(neg)
        not_el = [(e, p) for e, p in pairs if e != "not_eligible"]
        fnr = sum(1 for e, p in not_el if p == "not_eligible") / len(not_el)
        und = [(e, p) for e, p in pairs if e == "undetermined"]
        und_rec = sum(1 for e, p in und if p == "undetermined") / len(und) if und else None
        return {"accuracy": acc, "false_eligible_rate": fpr, "false_exclusion_rate": fnr, "undetermined_recall": und_rec}

    s = {k: score(v) for k, v in preds.items()}
    names = {"accuracy": "3-class accuracy", "false_eligible_rate": "False-positive eligibility rate",
             "false_exclusion_rate": "Wrongful exclusion rate", "undetermined_recall": "Undetermined cases flagged as undetermined"}
    counts = Counter(c["expected"] for c in g["cases"])
    return {"id": "E4", "title": "Eligibility classification",
            "description": "Proposed three-valued engine vs. the project's original v1 engine (baseline) on labelled persona x real-record cases. Extra: ablation of the proposed engine that treats unknown as satisfied.",
            "data": f"gold/eligibility_cases.json: {len(g['cases'])} cases ({dict(counts)}), 6 synthetic personas, 23 real records",
            "metrics": [{"name": names[k], "value": r3(s['proposed'][k]), "n": len(g["cases"])} for k in names],
            "baseline": [{"name": names[k], "value": r3(s['legacy_v1'][k])} for k in names],
            "extra": {"unknown_as_satisfied_ablation": {names[k]: r3(v) for k, v in s["unknown_as_satisfied"].items()},
                      "error_analysis": {
                          "undetermined_by_unknown_reasons": dict(Counter(
                              "+".join(t["unknown_reasons"]) for t in table if t["expected"] == "undetermined")),
                          "not_eligible_by_first_failed_criterion": dict(Counter(
                              t["first_failed"] for t in table if t["expected"] == "not_eligible"))}},
            "cases": table,
            "limitations": ["Labels were written by the developer who also wrote the rules: risk of shared interpretation. A human-labelled set is needed before claiming accuracy.",
                            "The v1 baseline has no 'undetermined' output, so its undetermined recall is 0 by construction; false-positive eligibility is the fairest comparison."]}


# --------------------------------------------------------------------------- E5 freshness ablation

def e5_freshness() -> dict:
    truth = {}
    gm = gold("entity_resolution.json")["mapping"]
    for s in parse_nsp_listing(REAL_HTML):
        ext = gm[find_key(s.title, gm)]
        if ext != "NEW":
            truth[ext] = s.deadline
    h = Harness()
    static = {s.external_id: (s.deadline, s.status_reported, trust.availability(s, TODAY)["state"])
              for s in h.db.scalars(select(Scholarship))}
    job = h.run(REAL_HTML)
    updated = {s.external_id: (s.deadline, trust.availability(s, TODAY)["state"]) for s in h.db.scalars(select(Scholarship))}
    ids = sorted(truth)
    true_state = {i: ("open" if truth[i] >= TODAY else "closed") for i in ids}

    def acc(pred: dict) -> float:
        return sum(1 for i in ids if pred[i] == true_state[i]) / len(ids)

    b0 = {i: ("open" if (static[i][1] or "").upper().startswith("ACTIVE") else "unknown") for i in ids}
    b1 = {i: static[i][2] for i in ids}
    pr = {i: updated[i][1] for i in ids}
    dl_static = sum(1 for i in ids if static[i][0] == truth[i]) / len(ids)
    dl_updated = sum(1 for i in ids if updated[i][0] == truth[i]) / len(ids)
    wrongly_closed_static = [i for i in ids if b1[i] == "closed" and true_state[i] == "open"]
    wrongly_closed_updated = [i for i in ids if pr[i] == "closed" and true_state[i] == "open"]

    # Downstream: persona x record pairs that a student could act on but would see as closed
    g = gold("eligibility_cases.json")
    from types import SimpleNamespace
    rows = {r["scholarship_id"]: r for r in dataset_rows()}
    hidden_static = hidden_updated = actionable = 0
    for persona in g["personas"].values():
        st = make_student(**persona)
        for i in ids:
            fields, _ = normalize_dataset_row(rows[i])
            if E.outcome(E.evaluate(st, SimpleNamespace(**fields), {})) == "not_eligible":
                continue
            actionable += 1
            hidden_static += b1[i] == "closed"
            hidden_updated += pr[i] == "closed"
    return {"id": "E5", "title": "Freshness ablation: static dataset vs. monitored data",
            "description": "On 2026-10-18, which application windows does each variant show correctly, using the official NSP listing archived that day as ground truth? B0 = dataset status text, B1 = static dataset dates, Proposed = dates after one monitored check (deterministic parser, auto-accepted under policy).",
            "data": f"{len(ids)} dataset records that appear on the archived NSP listing; job {job.status}",
            "metrics": [
                {"name": "Deadline equals official listing", "value": r3(dl_updated), "n": len(ids)},
                {"name": "Open/closed status correct", "value": r3(acc(pr)), "n": len(ids)},
                {"name": "Records wrongly shown as closed", "value": len(wrongly_closed_updated)},
                {"name": "Actionable matches hidden as 'closed' (6 personas)", "value": hidden_updated, "n": actionable},
            ],
            "baseline": [
                {"name": "Deadline equals official listing", "value": r3(dl_static)},
                {"name": "Open/closed status correct", "value": r3(acc(b1)), "note": "B1 static dates"},
                {"name": "Records wrongly shown as closed", "value": len(wrongly_closed_static)},
                {"name": "Actionable matches hidden as 'closed' (6 personas)", "value": hidden_static},
            ],
            "extra": {"b0_status_text_accuracy": r3(acc(b0)), "wrongly_closed_static": wrongly_closed_static,
                      "note_b0": "B0 marks every record ACTIVE. It is right for these NSP records only because all of them happen to be open; it is wrong for the Tata Trusts record, whose official page said on 2026-10-18 that the programme is closed for 2026-27 (observed by the page monitor, pending review), and it has no notion of passed deadlines."},
            "limitations": ["One snapshot date. Ground truth is the official listing, which can itself be wrong or late.",
                            "Covers only records present on the NSP listing (private schemes are not in this ground truth)."]}


# --------------------------------------------------------------------------- E6 LLM extraction (optional)

def _score_doc(d: dict, payload: dict) -> list[dict]:
    rows = []
    for f, exp in d["gold"].items():
        got = payload.get(f)
        if isinstance(exp, list):
            ok = got is not None and sorted(got) == sorted(exp)
        elif exp is None:
            ok = got in (None, [], "")
        else:
            ok = got is not None and abs(float(got) - float(exp)) < 1e-6
        rows.append({"field": f, "expected": exp, "got": got, "ok": bool(ok), "gold_is_null": exp is None})
    return rows


HISTORY = ROOT / "results" / "e6_runs.jsonl"


def e6_llm_extraction() -> dict:
    """Runs each document (retrying provider outages), appends the run to results/e6_runs.jsonl,
    and reports both this run and the pooled history of every archived run."""
    from app.services.extraction import extractor, llm

    g = gold("extraction.json")
    if not llm.status()["configured"]:
        return {"id": "E6", "title": "AI extraction accuracy", "description": "Skipped: no LLM key configured.",
                "data": "-", "metrics": [{"name": "Field accuracy", "value": None, "note": "not measured"}]}
    per_doc = []
    for d in g["documents"]:
        text = (ROOT / d["text_file"]).read_text(encoding="utf-8")
        attempts = []
        for attempt in range(1, 4):
            t0 = time.time()
            try:
                res = extractor.run_extraction(text, d["url"])
            except llm.LLMError as err:
                attempts.append({"attempt": attempt, "error_kind": err.kind, "error": str(err)[:160]})
                if not getattr(err, "transient", False):
                    break
                time.sleep(30)
                continue
            per_doc.append({"doc": d["id"], "model": f"{res.provider}/{res.model}", "seconds": round(time.time() - t0, 1),
                            "attempts": attempts + [{"attempt": attempt, "ok": True}],
                            "fields": _score_doc(d, res.payload), "unsupported_rejected": res.validation["unsupported"]})
            break
        else:
            per_doc.append({"doc": d["id"], "attempts": attempts, "error": "provider unavailable on all attempts"})
        if not per_doc or per_doc[-1]["doc"] != d["id"]:
            per_doc.append({"doc": d["id"], "attempts": attempts, "error": attempts[-1]["error"] if attempts else "failed"})
    run = {"run_at": datetime.now(timezone.utc).isoformat(), "documents": per_doc}
    HISTORY.parent.mkdir(exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(run, default=str) + "\n")
    return e6_summary(per_doc)


def e6_summary(per_doc_this_run: list[dict] | None = None) -> dict:
    runs = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()] if HISTORY.exists() else []
    scored = [(r["run_at"], d) for r in runs for d in r["documents"] if "fields" in d]
    failed = [(r["run_at"], d["doc"]) for r in runs for d in r["documents"] if "fields" not in d]
    fields = [f for _, d in scored for f in d["fields"]]
    correct = sum(f["ok"] for f in fields)
    halluc = sum(1 for f in fields if f["gold_is_null"] and not f["ok"])
    null_fields = sum(1 for f in fields if f["gold_is_null"])
    rejected = sum(len(d["unsupported_rejected"]) for _, d in scored)
    secs = [d["seconds"] for _, d in scored if "seconds" in d]
    docs_scored = sorted({d["doc"] for _, d in scored})
    misses = [{"run_at": t, "doc": d["doc"], "field": f["field"], "expected": f["expected"], "got": f["got"]}
              for t, d in scored for f in d["fields"] if not f["ok"]]
    return {"id": "E6", "title": "AI extraction accuracy (quote-verified)",
            "description": "The configured LLM extracts fields from 3 archived official documents; values without a verbatim, context-appropriate quote are rejected before scoring. Pooled over every archived run in results/e6_runs.jsonl (each document scored each time the provider was available).",
            "data": f"gold/extraction.json (3 documents, hand-checked); {len(runs)} archived runs; {len(scored)} scored document-runs; {len(failed)} document-runs lost to provider errors",
            "metrics": [
                {"name": "Field accuracy (pooled)", "value": r3(correct / len(fields)) if fields else None, "n": len(fields)},
                {"name": "Documents scored at least once", "value": len(docs_scored), "n": 3, "note": ", ".join(docs_scored)},
                {"name": "Hallucinated values where the document states nothing", "value": halluc, "n": null_fields},
                {"name": "Model values rejected by quote/context validation", "value": rejected},
                {"name": "Document-runs lost to provider errors (HTTP 503 overload or 429 quota)", "value": len(failed), "n": len(scored) + len(failed)},
                {"name": "Mean seconds per scored document", "value": r3(sum(secs) / len(secs)) if secs else None, "n": len(secs)},
            ],
            "misses": misses, "this_run": per_doc_this_run,
            "limitations": ["Three documents only; LLM output is non-deterministic and provider availability varied between runs.",
                            "Cost per document was not metered."]}


# --------------------------------------------------------------------------- E7 operations (live database)

def e7_operations() -> dict:
    from sqlalchemy import func
    from app.core.config import BACKEND_DIR

    db_path = BACKEND_DIR / "scholarscope.db"
    if not db_path.exists():
        return {"id": "E7", "title": "Operational metrics", "description": "No live database found.", "data": "-", "metrics": []}
    eng = create_engine(f"sqlite:///{db_path.as_posix()}")
    S = sessionmaker(bind=eng)()
    jobs = dict(S.execute(select(CrawlJob.status, func.count()).group_by(CrawlJob.status)).all())
    fin = jobs.get("succeeded", 0) + jobs.get("failed", 0)
    cands = dict(S.execute(select(Candidate.extraction_status, func.count()).group_by(Candidate.extraction_status)).all())
    pending = S.scalar(select(func.count()).select_from(ChangeEvent).where(ChangeEvent.review_status == "pending"))
    auto = S.scalar(select(func.count()).select_from(ChangeEvent).where(ChangeEvent.review_status == "auto_accepted"))
    S.close()
    return {"id": "E7", "title": "Operational metrics (live database)",
            "description": "Counts from the real crawl history of this installation (real network checks).",
            "data": f"{db_path.name}; jobs {jobs}",
            "metrics": [
                {"name": "Source-check success rate", "value": r3(jobs.get('succeeded', 0) / fin) if fin else None, "n": fin},
                {"name": "Changes auto-accepted under policy", "value": auto},
                {"name": "Changes waiting for review (manual-review load)", "value": pending},
                {"name": "Candidates with failed AI extraction", "value": cands.get("failed", 0), "n": sum(cands.values())},
                {"name": "Change-detection latency", "value": None, "note": "not measured: the true time a source changed is unknown"},
            ]}


# --------------------------------------------------------------------------- main

def to_markdown(result: dict) -> str:
    out = [f"# ScholarScope AI — evaluation results\n\nGenerated {result['generated_at']}.\n\n> {result['label_provenance']}\n"]
    for e in result["experiments"]:
        out.append(f"\n## {e['id']}. {e['title']}\n\n{e['description']}\n\n*Data:* {e['data']}\n")
        base = e.get("baseline")
        out.append("| Metric | Proposed |" + (" Baseline |" if base else "") + " n |\n|---|---|" + ("---|" if base else "") + "---|")
        for i, m in enumerate(e["metrics"]):
            v = "not measured" if m["value"] is None else m["value"]
            row = f"| {m['name']} | {v} |"
            if base:
                bv = base[i]["value"] if i < len(base) else ""
                row += f" {'not measured' if bv is None else bv} |"
            row += f" {m.get('n', '')} |"
            out.append(row)
        if e.get("extra"):
            out.append(f"\nExtra: `{json.dumps(e['extra'], default=str)}`")
        for l in e.get("limitations", []):
            out.append(f"\n- Limitation: {l}")
    return "\n".join(out) + "\n"


def dataset_profile() -> dict:
    """How completely the curated dataset states each rule after normalization (counts of records)."""
    prof: dict[str, Counter] = {k: Counter() for k in ("education_rule", "discipline_rule", "academic_rule", "income_rule")}
    with_questions = deadlines_passed = 0
    rows = dataset_rows()
    for row in rows:
        f, _ = normalize_dataset_row(row)
        for k in prof:
            prof[k][f[k]] += 1
        with_questions += any(c["kind"] == "question" for c in f["conditions"])
        deadlines_passed += bool(f["deadline"] and f["deadline"] < TODAY)
    return {"records": len(rows), **{k: dict(v) for k, v in prof.items()},
            "records_with_confirmation_questions": with_questions,
            f"deadlines_passed_on_{TODAY.isoformat()}": deadlines_passed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run E6 (calls the configured LLM)")
    args = ap.parse_args()
    t0 = time.time()
    exps = [e1_parser(), e2_entity_resolution(), e3_change_detection(), e4_eligibility(), e5_freshness()]
    previous = ROOT / "results" / "latest.json"
    if args.llm:
        exps.append(e6_llm_extraction())
    elif HISTORY.exists():
        exps.append(e6_summary())
    exps.append(e7_operations())
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": round(time.time() - t0, 1),
        "label_provenance": "All gold labels were produced by the developer (an AI assistant) from archived sources and are documented in evaluation/gold/*.json. They have not yet been independently verified by a human; treat results as preliminary.",
        "dataset_profile": dataset_profile(),
        "experiments": exps,
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "latest.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (ROOT / "results" / "report.md").write_text(to_markdown(result), encoding="utf-8")
    for e in exps:
        print(f"\n{e['id']} {e['title']}")
        base = e.get("baseline") or []
        for i, m in enumerate(e["metrics"]):
            b = f" | baseline {base[i]['value']}" if i < len(base) else ""
            print(f"  {m['name']}: {m['value']}{b}")


if __name__ == "__main__":
    main()
