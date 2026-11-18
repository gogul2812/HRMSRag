"""Prompt assembly, sensitivity routing, and declarative guardrails."""

from __future__ import annotations

import json
import re
from typing import Any

from rag_platform_schemas.orchestration import Citation, ContextChunk


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful enterprise assistant. Answer ONLY using the provided "
    "context. If the context is insufficient, say you do not have enough "
    "information. When citing, refer to sources as \"[source N]\" using the "
    "source numbers given in the context — never write out a raw document id "
    "or UUID in your answer. For general or capability questions (e.g. "
    "greetings, \"what can you help with\"), briefly describe what you can "
    "help with instead of refusing — you do not need document context for that."
)

# Greetings / capability questions never have a matching document chunk by
# nature — routing them through the retrieval relevance gate below means they
# always hit the hard "insufficient information" refusal before the LLM (and
# the system prompt guidance above) ever gets a turn. Recognize them here and
# skip retrieval instead of grounding them.
_GREETING_RE = re.compile(
    r"^(hi|hey|hello|yo|hiya|sup|good\s+(morning|afternoon|evening)|thanks|"
    r"thank\s*you|bye|goodbye)[\s!.?]*$",
    re.IGNORECASE,
)
_META_QUESTION_RE = re.compile(
    r"what\s+.{0,15}(you|u)\s+.{0,10}(help|do)"
    r"|how\s+can\s+(you|u)\s+help"
    r"|who\s+are\s+(you|u)"
    r"|what\s+are\s+(you|u)"
    r"|what\s+do\s+(you|u)\s+do",
    re.IGNORECASE,
)
_GREETING_PREFIX_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|hiya|sup)\b", re.IGNORECASE
)


def is_meta_or_greeting(query: str) -> bool:
    """True for greetings/capability questions that shouldn't require document grounding."""
    text = query.strip()
    if not text:
        return True
    if _GREETING_RE.match(text) or _META_QUESTION_RE.search(text):
        return True
    # Short message that starts with a greeting word ("hi are you there")
    # reads as chit-chat even though it isn't an exact greeting on its own —
    # but keep the word cap low so a real question that happens to open with
    # "hi" ("hi, what's our parental leave policy?") still gets grounded.
    words = text.split()
    return len(words) <= 6 and bool(_GREETING_PREFIX_RE.match(text))


def requires_local_only(chunks: list[ContextChunk] | list[dict[str, Any]]) -> bool:
    """Sensitivity rule: any employee doc_type → force local Ollama only."""
    for c in chunks:
        doc_type = c.doc_type if isinstance(c, ContextChunk) else c.get("doc_type")
        if str(doc_type or "").lower() == "employee":
            return True
    return False


def assemble_messages(
    *,
    query: str,
    chunks: list[ContextChunk],
    system_prompt: str | None,
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    system = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip()
    context_blocks: list[str] = []
    for i, c in enumerate(chunks, start=1):
        meta = f"[source {i} doc_id={c.doc_id}"
        if c.section:
            meta += f" section={c.section}"
        if c.page is not None:
            meta += f" page={c.page}"
        meta += "]"
        context_blocks.append(f"{meta}\n{c.text}")

    context = "\n\n".join(context_blocks) if context_blocks else "(no context retrieved)"
    user_content = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer grounded in the context above."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for turn in chat_history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_content})
    return messages


def build_faithfulness_check_messages(
    *, answer: str, chunks: list[ContextChunk]
) -> list[dict[str, str]]:
    """
    Second-pass groundedness check (Layer 8b). The relevance gate in
    retrieval-service stops the model from answering with no relevant context;
    this stops it from embellishing once it *has* relevant context.
    """
    context = "\n\n".join(f"[source {i}]\n{c.text}" for i, c in enumerate(chunks, start=1))
    system = (
        "You are a strict fact-checker, not the assistant that answered the user. "
        "You will see CONTEXT and an ANSWER someone else wrote from it. Judge only "
        "whether every factual claim in the ANSWER (numbers, names, dates, policy "
        "specifics) is directly supported by the CONTEXT — ignore greetings, "
        "disclaimers, and phrasing style. "
        "Respond with exactly one line: 'GROUNDED' if fully supported, or "
        "'UNGROUNDED: <short reason>' if it includes claims not found in the context."
    )
    user = f"CONTEXT:\n{context}\n\nANSWER:\n{answer}\n\nVerdict:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_faithfulness_verdict(raw: str) -> tuple[bool, str | None]:
    """Returns (is_grounded, reason_if_not). Unparseable judge output → grounded=True (fail open)."""
    text = raw.strip()
    if text.upper().startswith("UNGROUNDED"):
        reason = text.split(":", 1)[1].strip() if ":" in text else "unspecified"
        return False, reason[:200]
    return True, None


def build_citations(chunks: list[ContextChunk]) -> list[Citation]:
    citations: list[Citation] = []
    for c in chunks:
        citations.append(
            Citation(
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                section=c.section,
                page=c.page,
                score=c.score,
                excerpt=(c.text[:280] + ("…" if len(c.text) > 280 else "")),
            )
        )
    return citations


def apply_guardrails(
    answer: str, policy: dict[str, Any], *, query: str
) -> tuple[str, list[str]]:
    """
    Apply tenant declarative guardrail policy (Layer 8 lite).

    Supported policy_json keys:
      - refuse_topics: list[str]
      - required_disclaimer: str
      - blocked_phrases: list[str]
    """
    applied: list[str] = []
    text = answer

    refuse_topics = [str(t).lower() for t in (policy.get("refuse_topics") or [])]
    if refuse_topics:
        hay = f"{query}\n{answer}".lower()
        for topic in refuse_topics:
            if topic and topic in hay:
                applied.append(f"refuse_topic:{topic}")
                text = (
                    "I cannot help with that topic under this tenant's guardrail policy. "
                    "Please rephrase or ask about something else."
                )
                break

    for phrase in policy.get("blocked_phrases") or []:
        if phrase and phrase.lower() in text.lower():
            applied.append(f"blocked_phrase:{phrase}")
            text = re.sub(re.escape(phrase), "[redacted]", text, flags=re.IGNORECASE)

    disclaimer = policy.get("required_disclaimer")
    if disclaimer and disclaimer not in text:
        text = f"{text.rstrip()}\n\n{disclaimer}"
        applied.append("required_disclaimer")

    return text, applied


def scrub_pii_for_logs(text: str) -> str:
    """Delegate to shared Presidio/regex scrubber."""
    try:
        from rag_platform_pii import scrub

        return scrub(text)
    except ImportError:
        text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
        text = re.sub(r"\b\+?\d[\d\-\s()]{8,}\b", "[PHONE]", text)
        return text


def parse_requirements_json(raw: str) -> dict[str, Any]:
    """Best-effort JSON extraction from LLM requirement-extraction output."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {
        "skills": [],
        "tech_stack": [],
        "domain": None,
        "timeline": None,
        "raw": raw[:2000],
    }
