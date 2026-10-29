"""Readable-text extraction from HTML and PDF, plus normalization used for cosmetic-change filtering."""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

BOILERPLATE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe", "button"]
BOILERPLATE_HINTS = re.compile(r"(^|[-_ ])(nav|menu|footer|header|breadcrumb|cookie|banner|social|share|sidebar|skip|accessib)", re.I)

# Volatile text that changes without any change in meaning.
VOLATILE = [
    re.compile(r"(last\s+(updated|modified|reviewed)|page\s+updated|updated\s+on)\s*[:\-]?\s*[^\n|]{0,40}", re.I),
    re.compile(r"(visitors?|hits?|views?)\s*(count(er)?)?\s*[:\-]?\s*[\d,]+", re.I),
    re.compile(r"©\s*\d{4}(\s*[-–]\s*\d{4})?"),
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\s*(am|pm|ist)?\b", re.I),
]


@dataclass
class ExtractedText:
    text: str
    quality: str  # ok | low_text | needs_ocr | empty
    pages: int = 0
    note: str = ""


def html_to_text(html: str) -> ExtractedText:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()
    for el in soup.find_all(True):
        if el.attrs is None:
            continue
        ident = " ".join([el.get("id") or ""] + list(el.get("class") or []))
        if ident.strip() and BOILERPLATE_HINTS.search(ident) and el.name not in ("body", "main", "html"):
            el.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in root.get_text("\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    if not text:
        return ExtractedText("", "empty", note="No readable text (page may require JavaScript rendering)")
    if len(text) < 200:
        return ExtractedText(text, "low_text", note="Very little readable text; may be JavaScript-rendered")
    return ExtractedText(text, "ok")


def pdf_to_text(data: bytes, max_pages: int = 80) -> ExtractedText:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return ExtractedText("", "empty", note="PDF is encrypted")
        parts, low_pages = [], 0
        n = min(len(reader.pages), max_pages)
        for i in range(n):
            page_text = (reader.pages[i].extract_text() or "").strip()
            if len(page_text) < 40:
                low_pages += 1
            parts.append(f"[page {i + 1}]\n{page_text}")
    except (PdfReadError, ValueError, KeyError) as exc:
        return ExtractedText("", "empty", note=f"Could not parse PDF: {exc}")
    text = "\n\n".join(parts)
    if n and low_pages / n > 0.6:
        return ExtractedText(text, "needs_ocr", pages=n,
                             note=f"{low_pages}/{n} pages have almost no text layer; OCR would be required (not configured)")
    return ExtractedText(text, "ok", pages=n, note="" if len(reader.pages) <= max_pages else f"Truncated to {max_pages} pages")


def extract(content: bytes, content_type: str, url: str = "") -> ExtractedText:
    ct = (content_type or "").lower()
    if "pdf" in ct or url.lower().endswith(".pdf") or content[:5] == b"%PDF-":
        return pdf_to_text(content)
    for enc in ("utf-8", "latin-1"):
        try:
            return html_to_text(content.decode(enc))
        except UnicodeDecodeError:
            continue
    return ExtractedText("", "empty", note="Undecodable content")


def normalize_for_hash(text: str) -> str:
    t = text
    for rx in VOLATILE:
        t = rx.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode()).hexdigest()


DEADLINE_SENTENCE = re.compile(
    r"[^.\n]*(last\s+date|deadline|closing\s+date|apply\s+(by|before)|applications?\s+(close|closes|will\s+close))[^.\n]*",
    re.I)
DATE_IN_TEXT = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?[\s\-/.](?:\d{1,2}|jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)[\s\-/.,]+\d{4})\b",
    re.I)


def find_deadline_statements(text: str) -> list[tuple[str, str]]:
    """Sentences that state a deadline, with the date string found in them. Deterministic, no inference."""
    out = []
    for m in DEADLINE_SENTENCE.finditer(text):
        sentence = m.group(0).strip()
        for d in DATE_IN_TEXT.findall(sentence):
            out.append((sentence[:300], d))
    return out


CLOSURE_SENTENCE = re.compile(
    r"[^.\n]*(stands?\s+closed|(applications?|submissions?)\s+(is|are)\s+(now\s+)?(closed|no\s+longer\s+accepted)|"
    r"no\s+longer\s+accept(ed|ing)\s+applications?)[^.\n]*", re.I)


def find_closure_statements(text: str) -> list[str]:
    """Sentences in which the page itself says applications are closed."""
    return [m.group(0).strip()[:300] for m in CLOSURE_SENTENCE.finditer(text)]
