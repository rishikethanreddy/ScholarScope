"""API tests through FastAPI's TestClient with an isolated database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import ratelimit
from app.database import get_db
from app.main import app
from app.models import Candidate, Scholarship
from app.services.crawl import orchestrator
from app.services.sources.fetcher import SafeFetcher
from tests.conftest import copy_fixture, make_source


@pytest.fixture()
def client(session_factory, settings, monkeypatch):
    def _db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    # Run crawl jobs synchronously against the test database
    monkeypatch.setattr(orchestrator, "submit", lambda job_id: orchestrator.run_job(
        job_id, session_factory, SafeFetcher(settings, sleep=lambda s: None)))
    ratelimit.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def auth(client, email="student@test.local", password="student-pass-1"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def admin_headers(client, admin_user):
    r = client.post("/api/auth/login", json={"email": admin_user.email, "password": "admin-password-1"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health_and_public_catalogue(client, imported):
    assert client.get("/api/health").json()["status"] == "ok"
    data = client.get("/api/scholarships", params={"education_level": "PRE_MATRIC"}).json()
    assert data["total"] >= 3 and all("PRE_MATRIC" in s["education_levels"] for s in data["items"])
    one = data["items"][0]
    detail = client.get(f"/api/scholarships/{one['id']}").json()
    assert detail["evidence"]["current"] and detail["trust"]["primary"] and detail["versions"][0]["version"] == 1
    assert client.get("/api/scholarships/nope").status_code == 404
    stats = client.get("/api/stats/public").json()
    assert stats["published_scholarships"] == 31 and stats["llm"]["configured"] is False


def test_auth_validation_and_errors(client):
    assert client.post("/api/auth/register", json={"email": "bad", "password": "x" * 12}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    auth(client, "a@b.co", "long-enough-1")
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "long-enough-1"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "a@b.co", "password": "wrong-password"}).status_code == 401
    assert client.get("/api/me/profile").status_code == 401
    assert client.get("/api/me/profile", headers={"Authorization": "Bearer forged.token.value"}).status_code == 401


def test_login_rate_limited(client):
    codes = [client.post("/api/auth/login", json={"email": "x@y.co", "password": "nope-nope"}).status_code
             for _ in range(22)]
    assert codes[-1] == 429


def test_admin_routes_require_admin_role(client, imported):
    h = auth(client)
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview", headers=h).status_code == 403
    assert client.post("/api/admin/sources/x/check", headers=h).status_code == 403


def test_student_flow_profile_recommendations_answers_saved(client, imported):
    h = auth(client)
    assert client.get("/api/me/recommendations", headers=h).status_code == 404  # no profile yet
    bad = client.put("/api/me/profile", headers=h, json={"education_level": "PHD_PLUS"})
    assert bad.status_code == 422
    assert client.put("/api/me/profile", headers=h, json={"aadhaar": "1234"}).status_code == 422  # no extra PII fields
    p = client.put("/api/me/profile", headers=h, json={
        "education_level": "UG", "year_of_study": 1, "discipline": "ENGINEERING_TECHNOLOGY", "gender": "FEMALE",
        "annual_family_income": 300000, "qualifying_exam_percentage": 82, "state": "tamil nadu", "category": "GENERAL",
        "has_disability": False, "is_indian_citizen": True, "special_circumstances_none": True}).json()
    assert p["state"] == "Tamil Nadu"
    rec = client.get("/api/me/recommendations", headers=h).json()
    by_ext = {r["scholarship"]["external_id"]: r for r in rec["results"]}
    pragati = by_ext["IND-NSP-003"]  # AICTE Pragati degree: girls, technical, income <= 8L, two-girls question
    assert pragati["outcome"] == "potential_match"
    q = next(c for c in pragati["criteria"] if c["unknown_reason"] == "needs_confirmation")
    assert "two girls" in q["resolve"]["question"]["text"]
    assert by_ext["IND-NSP-005"]["outcome"] == "not_eligible"  # Saksham requires disability
    assert by_ext["IND-NSP-005"]["relevance"] is None
    assert rec["updates"]["items"] == []  # first visit only stores a baseline

    r = client.put("/api/me/answers", headers=h, json={"scholarship_id": pragati["scholarship_id"],
                                                       "criterion_key": q["resolve"]["question"]["key"], "answer": "yes"})
    assert r.status_code == 200
    one = client.get(f"/api/me/recommendations/{pragati['scholarship_id']}", headers=h).json()
    assert one["outcome"] in ("eligible", "eligible_pending_verification")
    assert all(c["evidence"] for c in one["criteria"] if c["key"] in ("income", "gender"))

    saved = client.post("/api/me/saved", headers=h, json={"scholarship_id": pragati["scholarship_id"]}).json()
    client.patch(f"/api/me/saved/{saved['id']}", headers=h, json={"status": "applied"})
    lst = client.get("/api/me/saved", headers=h).json()
    assert lst[0]["status"] == "applied"
    assert client.delete("/api/me/account", headers=h).json()["deleted"]
    assert client.get("/api/me/profile", headers=h).status_code == 401


def test_profile_update_rejects_server_managed_fields(client, imported):
    """The UI must not send id/updated_at back (it strips them); the API stays strict about unknown fields."""
    h = auth(client)
    first = client.put("/api/me/profile", headers=h, json={"education_level": "UG"}).json()
    assert "id" in first and "updated_at" in first
    echoed = client.put("/api/me/profile", headers=h, json=first)
    assert echoed.status_code == 422 and "Extra inputs are not permitted" in str(echoed.json())
    editable = {k: v for k, v in first.items() if k not in ("id", "updated_at")}
    assert client.put("/api/me/profile", headers=h, json={**editable, "state": "Kerala"}).status_code == 200


def test_check_document_requires_pdf_and_configured_llm(client, imported):
    h = auth(client)
    client.put("/api/me/profile", headers=h, json={"education_level": "UG"})
    r = client.post("/api/me/check-document", headers=h, files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/api/me/check-document", headers=h, files={"file": ("x.pdf", b"%PDF-1.4 tiny", "application/pdf")})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]  # never a mock result


def test_admin_end_to_end_review_flow(client, imported, admin_user, db, settings):
    h = admin_headers(client, admin_user)
    copy_fixture(settings, "nsp_listing_real_2026-10-18.html", "nsp.html")
    src = make_source(db, settings)
    job = client.post(f"/api/admin/sources/{src.id}/check", headers=h).json()
    detail = client.get(f"/api/admin/jobs/{job['id']}", headers=h).json()
    assert detail["status"] == "succeeded" and detail["log"]
    assert client.post(f"/api/admin/jobs/{job['id']}/retry", headers=h).status_code == 409  # only failed jobs

    cands = client.get("/api/admin/candidates", headers=h).json()
    nmms = next(c for c in cands if c["title"].startswith("National Means"))
    # Validation blocks publication without required fields
    r = client.post(f"/api/admin/candidates/{nmms['id']}/approve", headers=h,
                    json={"payload": {**nmms["payload"], "provider": ""}})
    assert r.status_code == 422 and "provider" in r.json()["detail"]
    # Extraction without an LLM key fails clearly
    ex = client.post(f"/api/admin/candidates/{nmms['id']}/extract", headers=h).json()
    assert ex["extraction_status"] == "failed"
    # Admin enters criteria manually and approves
    payload = {**nmms["payload"], "education_rule": "levels", "education_levels": ["PRE_MATRIC", "POST_MATRIC_SCHOOL"],
               "income_rule": "limit", "income_limit": 350000}
    ok = client.post(f"/api/admin/candidates/{nmms['id']}/approve", headers=h, json={"payload": payload, "note": "checked"})
    assert ok.status_code == 200
    sid = ok.json()["scholarship_id"]
    pub = client.get(f"/api/scholarships/{sid}").json()
    assert pub["scholarship"]["origin"] == "crawler" and pub["scholarship"]["deadline"] == "2026-10-31"
    methods = {e["field"]: e["method"] for e in pub["evidence"]["current"]}
    assert methods["deadline"] == "nsp_listing_parser" and methods["income_limit"] == "manual"
    feed = client.get("/api/feed/changes").json()
    assert any(n["id"] == sid for n in feed["new_scholarships"]) and feed["changes"]

    st = next(c for c in cands if c["title"].startswith("National Fellowship"))
    target = st["possible_matches"][0]["scholarship_id"]
    linked = client.post(f"/api/admin/candidates/{st['id']}/link", headers=h, json={"scholarship_id": target})
    assert linked.status_code == 200
    assert client.get(f"/api/scholarships/{target}").json()["trust"]["primary"] == "official_source_confirmed"

    overview = client.get("/api/admin/overview", headers=h).json()
    assert overview["jobs"]["all_time"]["succeeded"] == 1 and overview["review"]["pending_candidates"] == 2
    audit = client.get("/api/admin/audit", headers=h).json()
    assert {"candidate.approve", "candidate.link", "source.check"} <= {a["action"] for a in audit}


def test_admin_change_review_and_source_controls(client, imported, admin_user, db, settings):
    h = admin_headers(client, admin_user)
    data = (settings.fixtures_dir / "x").parent
    s = db.scalar(select(Scholarship).where(Scholarship.external_id == "IND-PRI-003"))
    (data / "tata.html").write_text("<main>" + "Means grant details. " * 20 +
                                    "This scholarship programme stands closed for the year 2026-2027.</main>")
    src = make_source(db, settings, key="tata", connector="html_page", file="tata.html", classification="official",
                      linked=s.id)
    client.post(f"/api/admin/sources/{src.id}/check", headers=h)
    pending = client.get("/api/admin/changes", headers=h).json()
    ev = next(c for c in pending if c["field"] == "status_reported")
    assert client.post(f"/api/admin/changes/{ev['id']}/accept", headers=h, json={"note": "verified"}).status_code == 200
    assert client.post(f"/api/admin/changes/{ev['id']}/accept", headers=h, json={}).status_code == 422
    detail = client.get(f"/api/scholarships/{s.id}").json()
    assert detail["scholarship"]["availability"]["state"] == "closed" and detail["scholarship"]["version"] == 2

    assert client.post(f"/api/admin/sources/{src.id}/pause", headers=h, json={"note": "maintenance"}).json()["health_status"] == "paused"
    assert client.post(f"/api/admin/sources/{src.id}/resume", headers=h).json()["health_status"] == "unknown"
    bad = client.post("/api/admin/sources", headers=h, json={
        "key": "bad_src", "name": "Bad", "classification": "official", "base_url": "https://a.gov.in/",
        "target_urls": ["https://b.gov.in/x"], "allowed_url_patterns": ["https://a.gov.in/*"], "connector": "html_page"})
    assert bad.status_code == 422
    test = client.post(f"/api/admin/sources/{src.id}/test", headers=h).json()
    assert test["ok"] and test["is_fixture"] and test["parsed"]["closure_statements"]
