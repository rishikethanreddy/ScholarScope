# AI extraction and validation

Code: `app/services/extraction/` (`text.py`, `llm.py`, `extractor.py`). Schema version `scholarship-extraction/1.0`.

## Where AI is used, and where it is not

| Task | Method |
|---|---|
| NSP deadlines, opening dates, renewal windows, guideline links | Deterministic parser (no AI) |
| Page change detection, closure and deadline statements | Hashes, text diff, regular-expression rules (no AI) |
| Eligibility decisions and ranking | Deterministic rules (no AI) |
| Eligibility rules inside unstructured guideline PDFs/pages | **LLM**, then strict validation, then human review |
| Student "check a PDF" tool | **LLM**, validated, shown as unverified, nothing stored |

## Pipeline

1. **Text extraction.** HTML: boilerplate tags/classes removed, main/article preferred; <200 chars ⇒ `low_text`
   (likely JavaScript-rendered). PDF: per-page text with `[page N]` markers; >60% near-empty pages ⇒ `needs_ocr`
   (OCR is not configured, so extraction is refused rather than run on empty text).
2. **Bounding.** Text over `LLM_MAX_INPUT_CHARS` (60 000) is reduced to the paragraphs with the most eligibility
   keywords, in original order.
3. **Prompt.** The document is wrapped in `<<<DOCUMENT_START>>> … <<<DOCUMENT_END>>>`; the system prompt states that
   the document is untrusted data, that instructions inside it must be ignored, that missing facts must be `null`, and
   that every value needs a verbatim quote (≤300 chars) and page number. Temperature 0, JSON output.
4. **Validation** (`extractor.validate`), per field:
   - quote present and found in the document (whitespace/punctuation-normalised);
   - quote and its source sentence free of instruction-like text (prompt-injection check);
   - quote contains context words for the field (e.g. a deadline quote must mention a last date/closing; a bare date
     is not evidence of a deadline);
   - types and plausible ranges (percentage 0–100, CGPA 0–10, income ₹1 000–₹10 crore, dates 2015–2035 and the date
     must appear in the quote);
   - vocabulary codes only (unknown codes dropped).
   Failing values are **removed** and listed under `unsupported` with the reason, for the reviewer to see.
5. **Payload.** Valid values are mapped to the scholarship schema (`to_payload`) with per-field evidence.
6. **Candidate.** Saved as a pending candidate. Listing-observed dates stay authoritative; guideline values fill gaps;
   disagreements are added as warnings.
7. **Human review and publication.** See [TRUST_MODEL.md](TRUST_MODEL.md).

## Providers and configuration

`LLM_PROVIDER=gemini|anthropic`, `LLM_API_KEY` (legacy `AI_API_KEY` accepted), optional `LLM_MODEL`. Calls are made
from the backend only, with transient 429/5xx retried twice with backoff. **There is no mock or fallback output.** With
no key the extraction step records `not_configured` and the admin enters data manually; the student PDF tool returns
HTTP 503 with an explanation.

## Measured behaviour (evaluation E6, archived runs as of 2026-10-20)

Every `--llm` run is now appended to `evaluation/results/e6_runs.jsonl`, and E6 pools all archived runs. Over 3 runs
on 3 official documents (AICTE Swanath PDF, NMMSS PDF, DEPwD page), 5 document-runs were scored and **20 of 21 fields
were correct**. 4 of 9 document-runs were lost to provider overload (HTTP 503) or quota (HTTP 429); these were
recorded as failures, never guessed.

The one error matters. In one of two scored Swanath runs, the model returned a minimum disability of 80 %, quoting the
clause about a *parent* disabled above 80 % in an accident. The quote exists and contains disability vocabulary, so
**all validation checks passed**. Quote verification proves that a statement exists, not whom it is about. This is why
extracted values always go to human review.

Earlier, unarchived runs on 2026-10-18 also showed the opposite trade-off: a correct value (NMMS ₹12 000/year) was
rejected because the model's quote "cleaned up" the PDF's garbled text layer. These runs predate archiving and are not
counted in E6.

## Known limitations

- No OCR: scanned PDFs are refused.
- Quote matching is lexical; heavily corrupted text layers reduce recall.
- Injection detection is pattern-based; it reduces, but cannot eliminate, the risk. Human review remains mandatory.
- Cost per document is not metered.
