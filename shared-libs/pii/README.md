# shared-libs/pii

Presidio-backed PII scrubbing with regex fallback (`PII_SCRUB_MODE=regex|auto|presidio|off`).

```python
from rag_platform_pii import scrub, scrub_messages

scrub("email ava@corp.test")  # → … [EMAIL]
scrub_messages(messages, force_local=False)  # cloud path
```

When `force_local=True` (employee sensitivity routing), messages are left intact
for local Ollama reasoning.
