"""PII scrubbing — Presidio when available, regex fallback otherwise."""

from __future__ import annotations

import os
import re
from functools import lru_cache


def _mode() -> str:
    return (os.environ.get("PII_SCRUB_MODE") or "auto").lower()


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b\+?\d[\d\-\s()]{8,}\d\b")
_SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Common name patterns after labels (employee documents)
_LABELED_NAME = re.compile(
    r"\b((?:employee|name|candidate)\s*[:=]\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    re.IGNORECASE,
)


def scrub_regex(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    text = _SSN_LIKE.sub("[ID]", text)
    text = _LABELED_NAME.sub(r"\1[NAME]", text)
    return text


@lru_cache(maxsize=1)
def _presidio_engines():
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        return AnalyzerEngine(), AnonymizerEngine()
    except Exception:
        return None


def scrub(text: str, *, entities: list[str] | None = None) -> str:
    """
    Mask PII in text for logs or cloud LLM payloads.

    Modes (PII_SCRUB_MODE):
      - auto: try Presidio, fall back to regex
      - regex / fake / stub: regex only
      - presidio: Presidio only (falls back if import fails)
      - off: no-op
    """
    if not text:
        return text
    mode = _mode()
    if mode in {"off", "none", "disable"}:
        return text
    if mode in {"regex", "fake", "stub"}:
        return scrub_regex(text)

    engines = _presidio_engines()
    if engines is None:
        return scrub_regex(text)

    analyzer, anonymizer = engines
    try:
        results = analyzer.analyze(
            text=text,
            language="en",
            entities=entities
            or ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "US_SSN", "LOCATION"],
        )
        if not results:
            return scrub_regex(text)
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
    except Exception:
        return scrub_regex(text)


def scrub_messages(messages: list[dict], *, force_local: bool = False) -> list[dict]:
    """
    Scrub user/system content before sending to a cloud LLM.
    When force_local=True (employee sensitivity), leave content unchanged —
    data stays on local Ollama and must remain usable for reasoning.
    """
    if force_local:
        return messages
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str) and role in {"user", "system", "assistant"}:
            out.append({**m, "content": scrub(content)})
        else:
            out.append(m)
    return out
