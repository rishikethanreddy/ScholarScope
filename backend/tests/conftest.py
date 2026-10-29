"""Shared fixtures. Every test gets an isolated in-memory database and a temporary data directory.

No test touches the network: HTTP is simulated with httpx.MockTransport and local fixture files.
Tests marked `network` hit real websites and run only with `pytest -m network`.
"""
from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnop")
os.environ["LLM_API_KEY"] = ""
os.environ["AI_API_KEY"] = ""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config as config_module
from app.database import Base
from app.models import Source, User

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "network: hits real external websites (run with -m network)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m") and "network" in config.getoption("-m"):
        return
    skip = pytest.mark.skip(reason="network test; run with -m network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    (data_dir / "fixtures").mkdir(parents=True)
    (data_dir / "snapshots").mkdir()
    s = dataclasses.replace(config_module.Settings(), data_dir=data_dir, crawler_allow_private_hosts=False,
                            crawler_min_domain_interval_seconds=0, llm_api_key="", scheduler_enabled=False)
    monkeypatch.setattr(config_module, "get_settings", lambda: s)
    for mod in ("app.services.connectors.base", "app.services.sources.fetcher", "app.services.extraction.llm",
                "app.services.extraction.extractor", "app.api.routers.me", "app.api.routers.admin",
                "app.api.routers.public", "app.core.security"):
        m = __import__(mod, fromlist=["get_settings"])
        if hasattr(m, "get_settings"):
            monkeypatch.setattr(m, "get_settings", lambda: s)
    return s


@pytest.fixture()
def session_factory(settings):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture()
def dataset_bytes() -> bytes:
    return (FIXTURES / "dataset.csv").read_bytes()


@pytest.fixture()
def imported(db, dataset_bytes):
    from app.services.ingestion.csv_import import import_dataset

    return import_dataset(db, dataset_bytes, file_name="dataset.csv", version="test-v1", dataset_name="test")


@pytest.fixture()
def admin_user(db):
    from app.core.security import hash_password

    u = User(email="admin@test.local", password_hash=hash_password("admin-password-1"), role="admin")
    db.add(u)
    db.commit()
    return u


def make_source(db, settings, key="fixture_nsp", connector="nsp_listing", file="nsp.html", classification="fixture",
                linked=None, **kw) -> Source:
    src = Source(key=key, name=f"Fixture {key}", classification=classification, base_url="fixture://",
                 target_urls=[f"fixture://{file}"], allowed_url_patterns=["fixture://*"], connector=connector,
                 linked_scholarship_id=linked, **kw)
    db.add(src)
    db.commit()
    return src


def put_fixture(settings, name: str, content: bytes | str) -> None:
    path = settings.fixtures_dir / name
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)


def copy_fixture(settings, src_name: str, dest_name: str) -> None:
    shutil.copy(FIXTURES / src_name, settings.fixtures_dir / dest_name)


def student(**kw):
    base = dict(education_level=None, current_class=None, year_of_study=None, course_name=None, discipline=None,
                qualifying_exam_percentage=None, cgpa=None, cgpa_scale=10.0, annual_family_income=None, state=None,
                gender=None, category=None, has_disability=None, disability_percent=None, is_indian_citizen=None,
                special_circumstances=[], special_circumstances_none=False)
    base.update(kw)
    return SimpleNamespace(**base)
