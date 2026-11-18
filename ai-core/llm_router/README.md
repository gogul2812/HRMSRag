# ai-core/llm_router

**Technology:** litellm

## Fallback chain

Groq → Gemini → OpenRouter → Ollama

`force_local=True` → Ollama only (employee / PII sensitivity routing).

## Interface

```python
from rag_platform_llm_router import generate
result = await generate(messages, tenant_id="...", force_local=False)
# result.content, result.provider, result.attempts
```

Set `LLM_ROUTER_MODE=fake` for offline tests.
Set `LLM_FAKE_FAIL_PRIMARY=1` (fake mode) or `LLM_FORCE_PRIMARY_FAIL=1` (litellm)
to exercise fallback.

## Module

Module 4 — Layer 7 / Stage 6
