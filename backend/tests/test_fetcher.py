import socket

import httpx
import pytest

from app.services.sources import fetcher as F

ALLOWED = ["https://example.gov.in/*"]
PUBLIC_DNS = lambda host, port: [(socket.AF_INET, 0, 0, "", ("93.184.216.34", port))]  # noqa: E731


@pytest.fixture(autouse=True)
def clear_robots_cache():
    F._ROBOTS.clear()
    yield
    F._ROBOTS.clear()


def make(settings, handler, robots="User-agent: *\nAllow: /\n", sleeps=None, resolver=PUBLIC_DNS):
    def route(request: httpx.Request):
        if request.url.path == "/robots.txt":
            if robots is None:
                return httpx.Response(404, text="nope", headers={"content-type": "text/html"})
            if isinstance(robots, int):
                return httpx.Response(robots)
            return httpx.Response(200, text=robots, headers={"content-type": "text/plain"})
        return handler(request)

    rec = sleeps if sleeps is not None else []
    return F.SafeFetcher(settings, transport=httpx.MockTransport(route), sleep=rec.append, resolver=resolver)


def test_ok_and_conditional_headers(settings):
    seen = {}

    def h(req):
        seen.update(req.headers)
        return httpx.Response(200, content=b"<html>hi</html>", headers={"etag": '"v1"', "content-type": "text/html"})

    r = make(settings, h).fetch("https://example.gov.in/page", ALLOWED, etag='"v0"', last_modified="Mon, 01 Jan 2026")
    assert r.status == 200 and r.etag == '"v1"'
    assert seen["if-none-match"] == '"v0"' and seen["if-modified-since"] == "Mon, 01 Jan 2026"
    assert "ScholarScopeBot" in seen["user-agent"]


def test_304_not_modified(settings):
    r = make(settings, lambda req: httpx.Response(304)).fetch("https://example.gov.in/p", ALLOWED, etag='"v1"')
    assert r.not_modified and r.content == b""


def test_retry_after_then_success(settings):
    calls, sleeps = [], []

    def h(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "7"})
        return httpx.Response(200, content=b"ok")

    r = make(settings, h, sleeps=sleeps).fetch("https://example.gov.in/p", ALLOWED)
    assert r.status == 200 and r.attempts == 2 and any(s >= 7 for s in sleeps)


def test_retry_after_too_long_gives_up(settings):
    h = lambda req: httpx.Response(429, headers={"retry-after": "3600"})  # noqa: E731
    with pytest.raises(F.FetchError) as e:
        make(settings, h).fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.kind == "rate_limited" and e.value.retry_after == 3600


def test_5xx_exhausts_retries_with_backoff(settings):
    calls, sleeps = [], []
    h = lambda req: calls.append(1) or httpx.Response(503)  # noqa: E731
    with pytest.raises(F.FetchError) as e:
        make(settings, h, sleeps=sleeps).fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.status == 503 and len(calls) == settings.crawler_max_retries + 1
    assert sleeps == sorted(sleeps)  # exponential backoff grows


def test_timeout_is_retried_then_reported(settings):
    def h(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(F.FetchError) as e:
        make(settings, h).fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.kind == "timeout"


@pytest.mark.parametrize("status,kind", [(403, "access_denied"), (401, "access_denied"), (404, "not_found")])
def test_no_retry_and_no_bypass_for_denied_or_missing(settings, status, kind):
    calls = []
    h = lambda req: calls.append(1) or httpx.Response(status)  # noqa: E731
    with pytest.raises(F.FetchError) as e:
        make(settings, h).fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.kind == kind and len(calls) == 1


def test_redirects_are_revalidated(settings):
    h = lambda req: httpx.Response(302, headers={"location": "https://evil.example.com/x"})  # noqa: E731
    with pytest.raises(F.FetchError) as e:
        make(settings, h).fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.kind == "blocked_by_policy"

    def ok(req):
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, content=b"moved")

    r = make(settings, ok).fetch("https://example.gov.in/old", ALLOWED)
    assert r.final_url.endswith("/new") and r.content == b"moved"


def test_redirect_loop_is_bounded(settings):
    h = lambda req: httpx.Response(302, headers={"location": "https://example.gov.in/loop"})  # noqa: E731
    with pytest.raises(F.FetchError, match="Too many redirects"):
        make(settings, h).fetch("https://example.gov.in/loop", ALLOWED)


def test_size_limit(settings):
    import dataclasses

    small = dataclasses.replace(settings, crawler_max_bytes=10)
    f = F.SafeFetcher(small, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, content=b"x" * 100) if req.url.path != "/robots.txt" else httpx.Response(404)),
        sleep=lambda s: None, resolver=PUBLIC_DNS)
    with pytest.raises(F.FetchError) as e:
        f.fetch("https://example.gov.in/big", ALLOWED)
    assert e.value.kind == "too_large"


def test_allowlist_and_scheme_checks(settings):
    f = make(settings, lambda req: httpx.Response(200))
    for url in ("https://other.gov.in/p", "file:///etc/passwd", "ftp://example.gov.in/x", "https://user:pw@example.gov.in/p"):
        with pytest.raises(F.FetchError) as e:
            f.fetch(url, ALLOWED + ["file:///*", "ftp://*"])
        assert e.value.kind == "blocked_by_policy"


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"])
def test_ssrf_private_addresses_blocked(settings, ip):
    fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
    f = make(settings, lambda req: httpx.Response(200), resolver=lambda h, p: [(fam, 0, 0, "", (ip, p))])
    with pytest.raises(F.FetchError) as e:
        f.fetch("https://example.gov.in/p", ALLOWED)
    assert e.value.kind == "ssrf_blocked"


def test_robots_disallow_and_unreachable(settings):
    f = make(settings, lambda req: httpx.Response(200), robots="User-agent: *\nDisallow: /private\n")
    with pytest.raises(F.FetchError) as e:
        f.fetch("https://example.gov.in/private/x", ALLOWED)
    assert e.value.kind == "robots_disallowed"
    assert f.fetch("https://example.gov.in/public", ALLOWED).status == 200
    F._ROBOTS.clear()
    with pytest.raises(F.FetchError):
        make(settings, lambda req: httpx.Response(200), robots=503).fetch("https://example.gov.in/p", ALLOWED)
    F._ROBOTS.clear()
    assert make(settings, lambda req: httpx.Response(200), robots=None).fetch("https://example.gov.in/p", ALLOWED).status == 200


def test_fixture_reads_and_traversal_blocked(settings):
    (settings.fixtures_dir / "a.html").write_text("<p>fixture</p>")
    f = F.SafeFetcher(settings, sleep=lambda s: None)
    r = f.fetch("fixture://a.html", ["fixture://*"])
    assert r.is_fixture and r.content == b"<p>fixture</p>"
    with pytest.raises(F.FetchError) as e:
        f.fetch("fixture://../../secret.txt", ["fixture://*"])
    assert e.value.kind == "blocked_by_policy"
    with pytest.raises(F.FetchError):
        f.fetch("fixture://a.html", ["https://example.gov.in/*"])


def test_parse_retry_after():
    assert F.parse_retry_after("120") == 120
    assert F.parse_retry_after(None) is None
    assert F.parse_retry_after("garbage") is None
