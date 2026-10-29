"""Entity resolution between source observations and catalogue records, and duplicate detection.

Similarity can only *propose* a match. Records are merged automatically only above the configured
auto-match threshold and only when no discriminating word conflicts (e.g. 'degree' vs 'diploma').
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional
from urllib.parse import urlsplit

from app.core.config import load_config_file
from app.services.normalize import normalize_name


def _policy() -> dict:
    return load_config_file("policies.json")["matching"]


def tokens(name: str) -> set[str]:
    stop = set(_policy()["stopwords"])
    return {t for t in normalize_name(name).split() if t not in stop}


def _singular(words: list[str]) -> set[str]:
    return {w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words}


def discriminator_conflict(a: str, b: str) -> Optional[str]:
    """Return a description if the names carry mutually exclusive discriminating words."""
    ta, tb = _singular(normalize_name(a).split()), _singular(normalize_name(b).split())
    for group in _policy()["discriminator_groups"]:
        ga, gb = ta & set(group), tb & set(group)
        if ga and gb and ga != gb:
            return f"{'/'.join(sorted(ga))} vs {'/'.join(sorted(gb))}"
        if bool(ga) != bool(gb) and (ga | gb) & {"pre", "post", "degree", "diploma", "ug", "pg"}:
            # One side is explicitly e.g. 'diploma' and the other is silent: not safe to auto-merge.
            return f"only one name states {'/'.join(sorted(ga | gb))}"
    return None


def name_similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round(0.5 * jaccard + 0.5 * seq, 4)


def normalize_url(url: Optional[str]) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/')}".lower().replace("%20", " ")


@dataclass
class MatchResult:
    record_id: str
    name: str
    score: float
    name_score: float
    url_match: bool
    conflict: Optional[str]

    @property
    def decision(self) -> str:
        p = _policy()
        if self.conflict:
            return "possible" if self.score >= p["possible_match_threshold"] else "none"
        if self.score >= p["auto_match_threshold"]:
            return "auto"
        if self.score >= p["possible_match_threshold"]:
            return "possible"
        return "none"

    def as_dict(self) -> dict:
        return {
            "scholarship_id": self.record_id, "name": self.name, "score": self.score,
            "name_score": self.name_score, "url_match": self.url_match, "conflict": self.conflict,
            "decision": self.decision,
        }


def score_pair(obs_name: str, obs_url: Optional[str], obs_provider: Optional[str],
               rec_id: str, rec_name: str, rec_urls: Iterable[Optional[str]], rec_provider: Optional[str]) -> MatchResult:
    p = _policy()
    ns = name_similarity(obs_name, rec_name)
    url_match = bool(obs_url) and normalize_url(obs_url) in {normalize_url(u) for u in rec_urls if u}
    score = ns + (p["url_bonus"] if url_match else 0.0)
    if obs_provider and rec_provider and tokens(obs_provider) & tokens(rec_provider):
        score += p["provider_bonus"]
    return MatchResult(rec_id, rec_name, round(min(score, 1.0), 4), ns, url_match,
                       discriminator_conflict(obs_name, rec_name))


def rank_matches(obs_name: str, obs_url: Optional[str], obs_provider: Optional[str], records: Iterable,
                 limit: int = 3) -> list[MatchResult]:
    results = [
        score_pair(obs_name, obs_url, obs_provider, r.id, r.name, [r.official_source_url, r.application_url], r.provider)
        for r in records
    ]
    results.sort(key=lambda m: (m.conflict is None, m.score), reverse=True)
    return [m for m in results[:limit] if m.score > 0.3]


def find_duplicate_pairs(records: list, threshold: Optional[float] = None) -> list[dict]:
    """Pairs of catalogue records that may describe the same opportunity (for admin review only)."""
    threshold = threshold if threshold is not None else _policy()["possible_match_threshold"] + 0.15
    pairs = []
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            m = score_pair(a.name, a.official_source_url, a.provider, b.id, b.name,
                           [b.official_source_url], b.provider)
            if m.score >= threshold and not m.conflict:
                pairs.append({"a_id": a.id, "a_name": a.name, "b_id": b.id, "b_name": b.name,
                              "score": m.score, "url_match": m.url_match})
    return sorted(pairs, key=lambda p: -p["score"])
