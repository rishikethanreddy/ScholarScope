"""Safe, polite HTTP fetching for registered sources only.

Guarantees:
  * Only URLs matching the source's allowed patterns are fetched (also re-checked on every redirect hop).
  * Hosts must resolve to public IP addresses (SSRF guard) unless explicitly allowed for local testing.
  * robots.txt is honoured (RFC 9309 semantics: 4xx => allowed, 5xx/unreachable => disallowed for now).
  * One request at a time per host, with a minimum interval between requests.
  * Retries with exponential backoff + jitter for 429/5xx/timeouts; Retry-After is respected.
  * Conditional requests (If-None-Match / If-Modified-Since); 304 is reported as not_modified.
  * Response size, redirect count and time are bounded.
  * Never bypasses CAPTCHAs, logins or bot protection: 401/403/451 are reported as access_denied.

`fixture://<relative path>` URLs read files from data/fixtures. They are labelled as fixtures everywhere and are
only for tests and the offline demo.
"""
from __future__ import annotations

import fnmatch
import ipaddress
import mimetypes
import random
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import Settings, get_settings

RETRY_STATUSES = {429, 500, 502, 503, 504}
DENIED_STATUSES = {401, 403, 451}
MAX_RETRY_AFTER_SECONDS = 120


class FetchError(Exception):
    def __init__(self, kind: str, message: str, status: Optional[int] = None, retry_after: Optional[float] = None):
        super().__init__(message)
        self.kind = kind  # blocked_by_policy|ssrf_blocked|robots_disallowed|access_denied|not_found|rate_limited|http_error|timeout|network|too_large
        self.status = status
        self.retry_after = retry_after


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content: bytes
    content_type: str
    headers: dict[str, str]
    not_modified: bool = False
    attempts: int = 1
    elapsed_ms: int = 0
    is_fixture: bool = False
    log: list[str] = field(default_factory=list)

    @property
    def etag(self) -> Optional[str]:
        return self.headers.get("etag")

    @property
    def last_modified(self) -> Optional[str]:
        return self.headers.get("last-modified")


def url_allowed(url: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(url, p) for p in patterns)


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


class _HostThrottle:
    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._last: dict[str, float] = {}
        self._guard = threading.Lock()

    def lock(self, host: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(host, threading.Lock())

    def wait(self, host: str, interval: float, sleep: Callable[[float], None]) -> None:
        last = self._last.get(host)
        if last is not None:
            delta = time.monotonic() - last
            if delta < interval:
                sleep(interval - delta)
        self._last[host] = time.monotonic()


_THROTTLE = _HostThrottle()
_ROBOTS: dict[str, tuple[float, Optional[RobotFileParser], str]] = {}
_ROBOTS_TTL = 24 * 3600


class SafeFetcher:
    def __init__(self, settings: Optional[Settings] = None, transport: Optional[httpx.BaseTransport] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 resolver: Callable[..., list] = socket.getaddrinfo, respect_robots: bool = True):
        self.s = settings or get_settings()
        self.sleep = sleep
        self.resolver = resolver
        self.respect_robots = respect_robots
        self.client = httpx.Client(
            transport=transport, follow_redirects=False, timeout=httpx.Timeout(self.s.crawler_timeout_seconds),
            headers={"User-Agent": self.s.crawler_user_agent, "Accept-Language": "en"},
        )

    def close(self):
        self.client.close()

    # ------------------------------------------------------------------ checks

    def _check_url(self, url: str, patterns: list[str]) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise FetchError("blocked_by_policy", f"Scheme not allowed: {parts.scheme}")
        if not parts.hostname:
            raise FetchError("blocked_by_policy", "URL has no host")
        if parts.username or parts.password:
            raise FetchError("blocked_by_policy", "Credentials in URL are not allowed")
        if not url_allowed(url, patterns):
            raise FetchError("blocked_by_policy", f"URL is outside the source's allowed patterns: {url}")
        if self.s.crawler_allow_private_hosts:
            return
        try:
            infos = self.resolver(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise FetchError("network", f"DNS resolution failed for {parts.hostname}: {exc}") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                raise FetchError("ssrf_blocked", f"{parts.hostname} resolves to non-public address {ip}")

    def _robots_allows(self, url: str, log: list[str]) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = _ROBOTS.get(origin)
        if cached and time.time() - cached[0] < _ROBOTS_TTL:
            parser, state = cached[1], cached[2]
        else:
            parser, state = None, "allow_all"
            try:
                resp = self.client.get(origin + "/robots.txt")
                if resp.status_code == 200 and "html" not in resp.headers.get("content-type", ""):
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                    state = "parsed"
                elif resp.status_code >= 500:
                    state = "unreachable"
                else:
                    state = "allow_all"  # 4xx or an HTML error page: no robots policy published
            except httpx.HTTPError:
                state = "unreachable"
            _ROBOTS[origin] = (time.time(), parser, state)
            log.append(f"robots.txt for {origin}: {state}")
        if state == "unreachable":
            return False
        if parser is None:
            return True
        return parser.can_fetch(self.s.crawler_user_agent, url)

    # ------------------------------------------------------------------ fetch

    def fetch(self, url: str, allowed_patterns: list[str], etag: Optional[str] = None,
              last_modified: Optional[str] = None) -> FetchResult:
        if url.startswith("fixture://"):
            return self._fetch_fixture(url, allowed_patterns)
        log: list[str] = []
        self._check_url(url, allowed_patterns)
        host = urlsplit(url).hostname or ""
        with _THROTTLE.lock(host):
            if not self._robots_allows(url, log):
                raise FetchError("robots_disallowed", f"robots.txt disallows or is unreachable for {url}")
            headers = {}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified
            return self._fetch_with_retries(url, allowed_patterns, headers, host, log)

    def _fetch_with_retries(self, url, patterns, headers, host, log) -> FetchResult:
        attempt = 0
        started = time.monotonic()
        while True:
            attempt += 1
            _THROTTLE.wait(host, self.s.crawler_min_domain_interval_seconds, self.sleep)
            try:
                result = self._single(url, patterns, headers, log)
                result.attempts = attempt
                result.elapsed_ms = int((time.monotonic() - started) * 1000)
                return result
            except FetchError as err:
                retryable = err.kind in ("timeout", "network") or (err.status in RETRY_STATUSES)
                if not retryable or attempt > self.s.crawler_max_retries:
                    raise
                delay = min(60.0, 2 ** (attempt - 1)) + random.uniform(0, 1)
                if err.retry_after is not None:
                    if err.retry_after > MAX_RETRY_AFTER_SECONDS:
                        raise FetchError("rate_limited", f"Server asked to retry after {err.retry_after:.0f}s",
                                         err.status, err.retry_after) from err
                    delay = max(delay, err.retry_after)
                log.append(f"attempt {attempt} failed ({err.kind} {err.status or ''}): retrying in {delay:.1f}s")
                self.sleep(delay)

    def _single(self, url: str, patterns: list[str], headers: dict, log: list[str]) -> FetchResult:
        current = url
        for hop in range(self.s.crawler_max_redirects + 1):
            try:
                with self.client.stream("GET", current, headers=headers) as resp:
                    status = resp.status_code
                    if status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("http_error", "Redirect without Location", status)
                        nxt = urljoin(current, location)
                        self._check_url(nxt, patterns)
                        log.append(f"redirect {status} -> {nxt}")
                        current = nxt
                        continue
                    if status == 304:
                        return FetchResult(url, current, 304, b"", resp.headers.get("content-type", ""),
                                           dict(resp.headers), not_modified=True, log=log)
                    if status in DENIED_STATUSES:
                        raise FetchError("access_denied", f"HTTP {status}: access denied (not bypassed)", status)
                    if status in (404, 410):
                        raise FetchError("not_found", f"HTTP {status}: not found", status)
                    if status in RETRY_STATUSES:
                        raise FetchError("rate_limited" if status == 429 else "http_error", f"HTTP {status}", status,
                                         parse_retry_after(resp.headers.get("retry-after")))
                    if status >= 400:
                        raise FetchError("http_error", f"HTTP {status}", status)
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > self.s.crawler_max_bytes:
                        raise FetchError("too_large", f"Content-Length {declared} exceeds limit", status)
                    chunks, total = [], 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > self.s.crawler_max_bytes:
                            raise FetchError("too_large", f"Body exceeds {self.s.crawler_max_bytes} bytes", status)
                        chunks.append(chunk)
                    return FetchResult(url, current, status, b"".join(chunks),
                                       resp.headers.get("content-type", ""), dict(resp.headers), log=log)
            except httpx.TimeoutException as exc:
                raise FetchError("timeout", f"Timed out fetching {current}") from exc
            except httpx.TransportError as exc:
                raise FetchError("network", f"Network error fetching {current}: {exc}") from exc
        raise FetchError("http_error", f"Too many redirects (>{self.s.crawler_max_redirects})")

    def _fetch_fixture(self, url: str, patterns: list[str]) -> FetchResult:
        if not url_allowed(url, patterns):
            raise FetchError("blocked_by_policy", f"Fixture URL not allowed for this source: {url}")
        base = self.s.fixtures_dir.resolve()
        path = (base / url.removeprefix("fixture://")).resolve()
        if base not in path.parents:
            raise FetchError("blocked_by_policy", "Fixture path escapes the fixtures directory")
        if not path.is_file():
            raise FetchError("not_found", f"Fixture file not found: {path.name}", 404)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FetchResult(url, url, 200, path.read_bytes(), ctype, {}, is_fixture=True,
                           log=[f"read local fixture {path.name} (not a live fetch)"])
