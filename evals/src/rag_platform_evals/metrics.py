"""Offline-friendly faithfulness / relevancy metrics (RAGAS stand-in + optional RAGAS)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


@dataclass
class CaseScore:
    case_id: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    must_include_hit_rate: float
    insufficient_ok: bool | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    tenant_key: str
    mode: str
    cases: list[CaseScore]
    faithfulness_mean: float
    answer_relevancy_mean: float
    context_precision_mean: float

    def to_dict(self) -> dict:
        return {
            "tenant_key": self.tenant_key,
            "mode": self.mode,
            "faithfulness_mean": round(self.faithfulness_mean, 4),
            "answer_relevancy_mean": round(self.answer_relevancy_mean, 4),
            "context_precision_mean": round(self.context_precision_mean, 4),
            "case_count": len(self.cases),
            "cases": [
                {
                    "id": c.case_id,
                    "faithfulness": round(c.faithfulness, 4),
                    "answer_relevancy": round(c.answer_relevancy, 4),
                    "context_precision": round(c.context_precision, 4),
                    "must_include_hit_rate": round(c.must_include_hit_rate, 4),
                    "insufficient_ok": c.insufficient_ok,
                    "notes": c.notes,
                }
                for c in self.cases
            ],
        }


def faithfulness_score(answer: str, contexts: list[str]) -> float:
    """
    Fraction of answer content tokens that appear in the union of contexts.
    Empty context + insufficient-style answer → 1.0; empty context + invented answer → 0.0.
    """
    ans = _tokens(answer)
    if not ans:
        return 0.0
    if not contexts:
        insufficient = any(
            p in answer.lower()
            for p in (
                "don't have enough",
                "do not have enough",
                "insufficient",
                "no relevant",
            )
        )
        return 1.0 if insufficient else 0.0
    ctx = set()
    for c in contexts:
        ctx |= _tokens(c)
    if not ctx:
        return 0.0
    overlap = len(ans & ctx)
    return overlap / max(len(ans), 1)


def answer_relevancy_score(question: str, answer: str) -> float:
    """Overlap between question tokens and answer tokens (rough relevancy proxy)."""
    q = _tokens(question)
    a = _tokens(answer)
    if not q or not a:
        return 0.0
    return len(q & a) / len(q)


def context_precision_score(contexts: list[str], expected_contexts: list[str]) -> float:
    """How well retrieved/used contexts cover expected ground-truth snippets."""
    if not expected_contexts:
        return 1.0 if not contexts else 0.5
    if not contexts:
        return 0.0
    hits = 0
    joined = " ".join(contexts).lower()
    for exp in expected_contexts:
        # Require a meaningful substring or high token overlap
        exp_l = exp.lower().strip()
        if len(exp_l) >= 12 and exp_l[:40] in joined:
            hits += 1
            continue
        exp_toks = _tokens(exp)
        ctx_toks = _tokens(joined)
        if exp_toks and len(exp_toks & ctx_toks) / len(exp_toks) >= 0.5:
            hits += 1
    return hits / len(expected_contexts)


def must_include_hit_rate(answer: str, must_include: list[str]) -> float:
    if not must_include:
        return 1.0
    lower = answer.lower()
    hits = sum(1 for m in must_include if m.lower() in lower)
    return hits / len(must_include)


def score_case(
    *,
    case_id: str,
    question: str,
    answer: str,
    contexts: list[str],
    expected_contexts: list[str],
    must_include: list[str],
    expect_insufficient: bool = False,
) -> CaseScore:
    notes: list[str] = []
    faith = faithfulness_score(answer, contexts if contexts else expected_contexts)
    relev = answer_relevancy_score(question, answer)
    # Prefer ground-truth contexts for precision when live retrieval contexts absent
    used_ctx = contexts if contexts else expected_contexts
    precision = context_precision_score(used_ctx, expected_contexts)
    include_rate = must_include_hit_rate(answer, must_include)

    insufficient_ok = None
    if expect_insufficient:
        insufficient_ok = any(
            p in answer.lower()
            for p in ("don't have enough", "do not have enough", "insufficient", "no relevant")
        )
        if not insufficient_ok:
            notes.append("expected insufficient-information style answer")
            faith = min(faith, 0.2)

    # Blend must-include into faithfulness for demo baseline stability
    faith = 0.7 * faith + 0.3 * include_rate

    return CaseScore(
        case_id=case_id,
        faithfulness=faith,
        answer_relevancy=relev,
        context_precision=precision,
        must_include_hit_rate=include_rate,
        insufficient_ok=insufficient_ok,
        notes=notes,
    )


def aggregate(tenant_key: str, mode: str, cases: list[CaseScore]) -> EvalReport:
    n = max(len(cases), 1)
    return EvalReport(
        tenant_key=tenant_key,
        mode=mode,
        cases=cases,
        faithfulness_mean=sum(c.faithfulness for c in cases) / n,
        answer_relevancy_mean=sum(c.answer_relevancy for c in cases) / n,
        context_precision_mean=sum(c.context_precision for c in cases) / n,
    )
