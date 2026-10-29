"""Real-source smoke tests. They hit live websites, so they are skipped unless run explicitly:

    pytest -m network -q

A failure here means a source changed its structure or is unreachable, not necessarily a code bug.
"""
import json
from pathlib import Path

import pytest

from app.services.connectors.nsp_listing import parse_nsp_listing
from app.services.extraction.text import extract
from app.services.sources.fetcher import SafeFetcher

SOURCES = json.loads((Path(__file__).parents[1] / "config" / "sources.json").read_text(encoding="utf-8"))["sources"]


@pytest.mark.network
def test_nsp_listing_is_reachable_and_parseable():
    src = next(s for s in SOURCES if s["key"] == "nsp_all_schemes")
    f = SafeFetcher()
    res = f.fetch(src["target_urls"][0], src["allowed_url_patterns"])
    schemes = parse_nsp_listing(res.content.decode("utf-8", errors="replace"))
    assert res.status == 200 and len(schemes) >= 15, "NSP layout may have changed; parser found too few schemes"
    assert sum(1 for s in schemes if s.deadline) >= 0.8 * len(schemes)


@pytest.mark.network
@pytest.mark.parametrize("key", [s["key"] for s in SOURCES if s.get("enabled", True) and s["connector"] != "nsp_listing"])
def test_enabled_page_sources_return_readable_text(key):
    src = next(s for s in SOURCES if s["key"] == key)
    res = SafeFetcher().fetch(src["target_urls"][0], src["allowed_url_patterns"])
    text = extract(res.content, res.content_type, src["target_urls"][0])
    assert text.quality in ("ok", "low_text"), f"{key}: {text.note}"
