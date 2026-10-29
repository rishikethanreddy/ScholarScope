"""Offline demonstration database (python -m app.cli demo-setup).

Creates backend/data/demo/demo.db with the real dataset and three LOCAL FIXTURE sources, all labelled as fixtures:

  demo_nsp_listing    archived copy of the real NSP listing page (captured 2026-10-18). Step 2 of the demo script
                      "checks" it; step 11 swaps in a synthetic revision (deadline extended, one scheme removed).
  demo_tata_page      synthetic copy of a scheme-owner page that states the programme is closed.
  demo_broken_source  points to a fixture file that does not exist, to show a failed source honestly.

Run the API against it with:  DATABASE_URL=sqlite:///data/demo/demo.db  DATA_DIR=data/demo  DEMO_MODE=true
Nothing in the demo database is a live internet check, and the UI shows a banner saying so.
"""
from __future__ import annotations

import shutil

from app.core.config import BACKEND_DIR

DEMO_DIR = BACKEND_DIR / "data" / "demo"
SNAPSHOT = BACKEND_DIR.parent / "evaluation" / "snapshots" / "nsp_all_scholarships_2026-10-18.html"
ROW = '<div class="row mb-4 border-1 border-bottom">'

TATA_PAGE = """<html><body><nav>Home | Our work | Grants</nav><main>
<h1>Individual education grants (DEMO FIXTURE: synthetic copy for offline demonstration)</h1>
<p>The Means Grant Programme provides partial financial assistance, based on students' needs, to Indian residents
pursuing their education anywhere in India. The scheme is open to school-going students from Standard VIII onwards and
college students up to graduation.</p>
<p>This scholarship programme stands closed for the year 2026-2027.</p>
</main><footer>Last updated: 18 Oct 2026</footer></body></html>"""


def revised_listing(html: str) -> str:
    """Synthetic revision used in demo step 11: AICTE Pragati (degree) deadline 31-10-2026 -> 15-11-2026,
    and the MNRE fellowship removed from the page."""

    def bounds(h: str, title: str) -> tuple[int, int]:
        at = h.index(title)
        end = h.find(ROW, at)
        return h.rindex(ROW, 0, at), end

    a, b = bounds(html, "Girl Students ( Technical Degree)")
    html = html[:a] + html[a:b].replace("31-10-2026", "15-11-2026") + html[b:]
    a, b = bounds(html, "National Renewable Energy Fellowship Scheme")
    return html[:a] + html[b:]


def setup() -> None:
    import os

    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    (DEMO_DIR / "fixtures").mkdir(parents=True)
    (DEMO_DIR / "snapshots").mkdir()
    html = SNAPSHOT.read_text(encoding="utf-8")
    (DEMO_DIR / "fixtures" / "nsp_listing.html").write_text(html, encoding="utf-8")
    (DEMO_DIR / "fixtures" / "nsp_listing_revision2.html").write_text(revised_listing(html), encoding="utf-8")
    (DEMO_DIR / "fixtures" / "nsp_listing_original.html").write_text(html, encoding="utf-8")
    (DEMO_DIR / "fixtures" / "tata.html").write_text(TATA_PAGE, encoding="utf-8")

    db_url = f"sqlite:///{(DEMO_DIR / 'demo.db').as_posix()}"
    os.environ["DATABASE_URL"] = db_url
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    from app.models import Scholarship, ScholarshipSource, Source
    from app.services.ingestion.csv_import import import_dataset

    Session = sessionmaker(bind=create_engine(db_url), autoflush=False, expire_on_commit=False)
    db = Session()
    dataset = BACKEND_DIR / "data" / "imports" / "india_scholarship_dataset_2026_27_researched.csv"
    import_dataset(db, dataset.read_bytes(), file_name=dataset.name, version="demo-v1", dataset_name="Demo import")
    tata = db.scalar(select(Scholarship).where(Scholarship.external_id == "IND-PRI-003"))
    sources = [
        Source(key="demo_nsp_listing", name="NSP listing — archived copy (LOCAL FIXTURE)", organization="NSP (archived 2026-10-18)",
               classification="fixture", base_url="fixture://", target_urls=["fixture://nsp_listing.html"],
               allowed_url_patterns=["fixture://*"], connector="nsp_listing", crawl_frequency_minutes=60 * 24 * 30,
               priority=100, access_notes="Offline demo. Copy of the real page captured 2026-10-18; not a live check."),
        Source(key="demo_tata_page", name="Tata Trusts grants page — synthetic copy (LOCAL FIXTURE)", organization="Tata Trusts",
               classification="fixture", base_url="fixture://", target_urls=["fixture://tata.html"],
               allowed_url_patterns=["fixture://*"], connector="html_page", crawl_frequency_minutes=60 * 24 * 30,
               linked_scholarship_id=tata.id, priority=60, access_notes="Offline demo fixture."),
        Source(key="demo_broken_source", name="Unreachable source (LOCAL FIXTURE, intentionally missing)",
               classification="fixture", base_url="fixture://", target_urls=["fixture://does-not-exist.html"],
               allowed_url_patterns=["fixture://*"], connector="html_page", crawl_frequency_minutes=60 * 24 * 30,
               priority=10, access_notes="Demonstrates how a failing source is reported."),
    ]
    db.add_all(sources)
    db.flush()
    db.add(ScholarshipSource(scholarship_id=tata.id, source_id=sources[1].id, external_key="fixture://tata.html",
                             match_method="configured"))
    db.commit()
    db.close()
    print(f"demo database ready: {DEMO_DIR / 'demo.db'}")
    print("start the API with:  DATABASE_URL=" + db_url + f"  DATA_DIR={DEMO_DIR.as_posix()}  DEMO_MODE=true  SCHEDULER_ENABLED=false")
    print("then create an admin:  python -m app.cli create-admin --email admin@demo.local   (with the same env vars)")


def use_revision(n: int = 2) -> None:
    """Swap the demo NSP fixture to the synthetic revision (step 11) or back to the original (n=1)."""
    src = DEMO_DIR / "fixtures" / ("nsp_listing_revision2.html" if n == 2 else "nsp_listing_original.html")
    shutil.copy(src, DEMO_DIR / "fixtures" / "nsp_listing.html")
    print(f"demo NSP fixture now serves {'the synthetic revision' if n == 2 else 'the original archived page'}")


if __name__ == "__main__":
    setup()
