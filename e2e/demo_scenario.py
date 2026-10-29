"""End-to-end test of the critical UI workflows, following the 14-step demonstration scenario (docs/DEMO_SCRIPT.md).

Prerequisites (see docs/DEMO_SCRIPT.md):
  1. python -m app.cli demo-setup              (fresh offline demo database with LOCAL FIXTURE sources)
  2. API on :8000 with DATABASE_URL/DATA_DIR pointing at data/demo, DEMO_MODE=true, SCHEDULER_ENABLED=false
  3. python -m app.cli create-admin --email admin@demo.local   (ADMIN_PASSWORD=demo-admin-pass-1)
  4. Frontend on :5173

Run:  backend/.venv/Scripts/python e2e/demo_scenario.py [--headed]
Screenshots are written to e2e/artifacts/. Exit code 0 means every assertion passed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

WEB = os.environ.get("E2E_WEB", "http://localhost:5173")
ADMIN = (os.environ.get("E2E_ADMIN_EMAIL", "admin@demo.local"), os.environ.get("E2E_ADMIN_PASSWORD", "demo-admin-pass-1"))
ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts"
BACKEND = ROOT.parent / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = BACKEND / ".venv" / "bin" / "python"
STEP = 0


def step(page: Page, title: str) -> None:
    global STEP
    STEP += 1
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(ART / f"{STEP:02d}-{title.replace(' ', '_')[:40]}.png"), full_page=True)
    print(f"  ✓ step {STEP}: {title}")


def login(page: Page, email: str, password: str) -> None:
    page.goto(f"{WEB}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda url: "/login" not in url)
    page.wait_for_load_state("networkidle")


def logout(page: Page) -> None:
    page.evaluate("localStorage.removeItem('scholarscope.token')")


def run_check(page: Page, source_name: str) -> None:
    page.goto(f"{WEB}/admin/sources")
    card = page.locator("div.rounded-2xl", has_text=source_name).first
    try:
        card.get_by_role("button", name="Run check").click(timeout=10_000)
    except Exception:
        page.screenshot(path=str(ART / "FAILED-run-check.png"), full_page=True)
        raise
    page.get_by_role("link", name="View job").click()
    expect(page.get_by_text("Job log")).to_be_visible()
    for _ in range(60):  # wait for the background job to finish
        if page.get_by_text("succeeded").first.is_visible() or page.get_by_text("failed").first.is_visible():
            break
        time.sleep(0.5)
        page.reload()


def demo_cli(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(BACKEND / 'data/demo/demo.db').as_posix()}",
           "DATA_DIR": str(BACKEND / "data" / "demo")}
    subprocess.run([str(PY), "-m", "app.cli", *args], cwd=BACKEND, env=env, check=True, capture_output=True)


def main(headed: bool = False) -> None:
    ART.mkdir(exist_ok=True)
    student_email = f"student-{uuid.uuid4().hex[:6]}@example.com"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # 1. Admin inspects the source registry
        login(page, *ADMIN)
        expect(page.get_by_text("Operations overview")).to_be_visible()
        page.goto(f"{WEB}/admin/sources")
        expect(page.get_by_text("NSP listing — archived copy (LOCAL FIXTURE)")).to_be_visible()
        expect(page.get_by_text("Local fixture (not live)").first).to_be_visible()
        expect(page.get_by_text("DEMO DATABASE")).to_be_visible()
        step(page, "admin inspects sources")

        # 2-3. A permitted check runs; known deadlines are corrected and new schemes become candidates
        run_check(page, "NSP listing — archived copy")
        expect(page.get_by_text("succeeded").first).to_be_visible()
        expect(page.get_by_text("deadline 2026-09-30 -> 2026-10-31").first).to_be_visible()
        expect(page.get_by_text("candidate: 'National Means Cum Merit Scholarship'")).to_be_visible()
        step(page, "check finds changes and new schemes")

        # 4-6. Candidate shows evidence; validation blocks publishing without required data
        page.goto(f"{WEB}/admin/review")
        page.get_by_text("National Means Cum Merit Scholarship").click()
        expect(page.get_by_text("Eligibility criteria are not on the listing page", exact=False)).to_be_visible()
        expect(page.get_by_text("Student Application Open till : 31-10-2026", exact=False).first).to_be_visible()
        page.get_by_label("Provider").fill("")
        page.get_by_role("button", name="Approve & publish").click()
        expect(page.get_by_text("Missing required field: provider")).to_be_visible()
        step(page, "validation catches missing field")

        # 7-8. Admin completes the record from the guideline and approves; it appears in the catalogue
        page.get_by_label("Provider").fill("Department of School Education & Literacy")
        page.get_by_label("Education rule").fill("levels")
        page.get_by_label("Education levels").fill("PRE_MATRIC, POST_MATRIC_SCHOOL")
        page.get_by_label("Income rule").fill("limit")
        page.get_by_label("Income ceiling").fill("350000")
        page.get_by_label("Review note").fill("Income and class range checked against NMMSS guideline (pages 1 and 4).")
        page.get_by_role("button", name="Approve & publish").click()
        expect(page.get_by_role("heading", name="National Means Cum Merit Scholarship")).to_be_visible()
        expect(page.get_by_text("Discovered by monitor").first).to_be_visible()
        step(page, "approved record published")
        logout(page)

        # 9-10. A student gets recommendations with criteria-level explanations and evidence
        page.goto(f"{WEB}/register")
        page.get_by_label("Email").fill(student_email)
        page.get_by_label("Password").fill("student-pass-123")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_text("Tell us what the rules need")).to_be_visible()
        page.get_by_label("Current education level").select_option("PRE_MATRIC")
        page.get_by_label("Current class").fill("9")
        page.get_by_label("Annual family income (₹)").fill("200000")
        page.get_by_label("State / UT of domicile").select_option("Bihar")
        page.get_by_label("Indian citizen").select_option("yes")
        page.get_by_label("None of these apply to me").check()
        page.get_by_role("button", name="Save and see my matches").click()
        expect(page.get_by_text("Your scholarship dashboard")).to_be_visible()
        step(page, "student dashboard")
        page.goto(f"{WEB}/discover?q=means")
        page.get_by_role("link", name="National Means Cum Merit Scholarship").click()
        expect(page.get_by_text("Family income").first).to_be_visible()
        expect(page.get_by_text("Your family income ₹200,000 is within the ₹350,000 ceiling.")).to_be_visible()
        page.get_by_role("button", name="Evidence · Entered by admin").first.click()
        step(page, "why this match with evidence")

        # 11-13. A later source revision changes a deadline; history keeps old and new values
        logout(page)
        demo_cli("demo-revision", "--n", "2")
        login(page, *ADMIN)
        run_check(page, "NSP listing — archived copy")
        expect(page.get_by_text("2026-10-31 -> 2026-11-15").first).to_be_visible()
        expect(page.get_by_text("no longer listed; change queued for review")).to_be_visible()
        step(page, "revision detected")
        page.goto(f"{WEB}/discover?q=pragati")
        page.get_by_role("link", name="AICTE - Pragati Scholarship Scheme for Girl Students (Technical Degree)").click()
        page.get_by_role("tab", name="History").click()
        expect(page.get_by_text("Deadline: 15 Nov 2026 (was 31 Oct 2026)")).to_be_visible()
        expect(page.get_by_text("Imported from dataset demo-v1")).to_be_visible()  # version 1 is kept
        step(page, "change history old and new")
        page.goto(f"{WEB}/admin/changes")
        expect(page.get_by_text("Listed on source").first).to_be_visible()
        step(page, "removal waits for review")

        # 14. A failing source is shown as failed, never as a successful check
        run_check(page, "Unreachable source")
        expect(page.get_by_text("failed").first).to_be_visible()
        expect(page.get_by_text("Fixture file not found", exact=False).first).to_be_visible()
        page.goto(f"{WEB}/admin/sources")
        expect(page.locator("div.rounded-2xl", has_text="Unreachable source").get_by_text("degraded")).to_be_visible()
        step(page, "failed source reported")

        # Student sees what changed for them
        logout(page)
        login(page, student_email, "student-pass-123")
        page.goto(f"{WEB}/changes")
        expect(page.get_by_text("What changed?")).to_be_visible()
        expect(page.get_by_text("National Means Cum Merit Scholarship").first).to_be_visible()
        step(page, "public change feed")
        demo_cli("demo-revision", "--n", "1")

        # The only expected browser error is the 422 from step 3 (approval refused by validation).
        unexpected = [e for e in errors if "status of 422" not in e]
        assert len(errors) - len(unexpected) == 1, f"expected exactly one validation 422, got {errors}"
        assert not unexpected, f"console errors: {unexpected[:5]}"
        browser.close()
    print(f"\nAll {STEP} steps passed. Screenshots in {ART}")


if __name__ == "__main__":
    main(headed="--headed" in sys.argv)
