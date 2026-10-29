"""Provider-agnostic LLM client. Backend-only; keys come from environment variables.

There is deliberately no mock fallback: if no provider is configured, or the call fails, an LLMError is raised
and the caller records a failed extraction. Nothing is ever presented as model output unless a model produced it.
"""
from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from app.core.config import Settings, get_settings

DEFAULT_MODELS = {
    # Model ids change; override with LLM_MODEL. The Gemini default is the replacement model named by the
    # Gemini API's own deprecation error recorded in the legacy ai_error.log.
    "gemini": "gemini-3.6-flash",
    "anthropic": "claude-sonnet-5-5",
}


class LLMError(Exception):
    def __init__(self, kind: str, message: str, transient: bool = False):
        super().__init__(message)
        self.kind = kind  # not_configured | provider_error | timeout | invalid_json | quota
        self.transient = transient


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_chars: int


def status(settings: Optional[Settings] = None) -> dict:
    s = settings or get_settings()
    configured = bool(s.llm_api_key) and s.llm_provider in DEFAULT_MODELS
    return {"provider": s.llm_provider, "model": s.llm_model or DEFAULT_MODELS.get(s.llm_provider),
            "configured": configured}


def complete_json(system: str, user: str, settings: Optional[Settings] = None,
                  transport: Optional[httpx.BaseTransport] = None, retries: int = 2,
                  sleep: Callable[[float], None] = time.sleep) -> LLMResponse:
    s = settings or get_settings()
    if s.llm_provider not in DEFAULT_MODELS:
        raise LLMError("not_configured", f"Unsupported LLM_PROVIDER '{s.llm_provider}' (use gemini or anthropic)")
    if not s.llm_api_key:
        raise LLMError("not_configured", "No LLM API key configured (set LLM_API_KEY). Extraction was not run.")
    model = s.llm_model or DEFAULT_MODELS[s.llm_provider]
    call = _gemini if s.llm_provider == "gemini" else _anthropic
    with httpx.Client(timeout=s.llm_timeout_seconds, transport=transport) as client:
        for attempt in range(1, retries + 2):
            try:
                text = call(client, s.llm_api_key, model, system, user)
                break
            except LLMError as err:
                if not err.transient or attempt > retries:
                    raise
                sleep(min(30.0, 2.0 * 2 ** (attempt - 1)) + random.uniform(0, 1))
            except httpx.TimeoutException as exc:
                raise LLMError("timeout", f"LLM request timed out after {s.llm_timeout_seconds}s") from exc
            except httpx.HTTPError as exc:
                raise LLMError("provider_error", f"LLM transport error: {exc}") from exc
    return LLMResponse(text=text, provider=s.llm_provider, model=model, input_chars=len(system) + len(user))


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code == 429:
        raise LLMError("quota", f"Provider rate limit/quota exceeded (HTTP 429): {resp.text[:300]}", transient=True)
    if resp.status_code in (500, 502, 503, 504):
        raise LLMError("provider_error", f"Provider temporarily unavailable (HTTP {resp.status_code}): "
                       f"{resp.text[:300]}", transient=True)
    if resp.status_code >= 400:
        raise LLMError("provider_error", f"Provider returned HTTP {resp.status_code}: {resp.text[:300]}")


def _gemini(client: httpx.Client, key: str, model: str, system: str, user: str) -> str:
    resp = client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "content-type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
    )
    _raise_for(resp)
    data = resp.json()
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("provider_error", f"Unexpected Gemini response shape: {str(data)[:300]}") from exc


def _anthropic(client: httpx.Client, key: str, model: str, system: str, user: str) -> str:
    resp = client.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 4096, "temperature": 0, "system": system,
              "messages": [{"role": "user", "content": user}]},
    )
    _raise_for(resp)
    data = resp.json()
    try:
        return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise LLMError("provider_error", f"Unexpected Anthropic response shape: {str(data)[:300]}") from exc


def parse_json_object(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise LLMError("invalid_json", "Model output is not JSON")
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError("invalid_json", f"Model output is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise LLMError("invalid_json", "Model output JSON is not an object")
    return obj
