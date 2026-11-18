# Module 7 — Security & Guardrails

> Depends on: Module 5 (data isolation), Module 4 (guardrail layer).

## 1. Authentication & authorization

- JWT issued by `auth-service`, containing `user_id`, `tenant_id`, `role`.
- The gateway validates the JWT once and forwards trusted headers
  downstream — no service re-validates the token, but every service trusts
  only the gateway's headers, not a client-supplied tenant ID.
- Role check (`admin` vs `end_user`) enforced at the gateway route level
  first, then again at the service level as defense in depth (e.g.
  `admin-config-service` rejects any request without `role: admin`, even if
  it somehow bypassed the gateway).

## 2. Secrets management

- All API keys (Groq, Gemini, OpenRouter) and database credentials live in
  a secrets manager (Kubernetes Secrets backed by a vault, or a managed
  secrets service), never in code or `.env` files committed to the repo.
- Per-tenant secrets (if a tenant ever needs its own dedicated API key,
  e.g. a HIPAA-eligible Azure OpenAI key for a healthcare tenant) are
  scoped and retrieved by `tenant_id` at request time by
  `llm-orchestrator-service`.

## 3. PII handling (the HR/employee data case)

This platform explicitly holds employee experience/resource documents for
some tenants — treat this as the default assumption, not an edge case.

- **Sensitivity routing** (Module 4, Layer 7): any answer whose retrieved
  context includes `doc_type: employee` chunks is forced onto the local
  Ollama model — no cloud LLM call is attempted for that request, full
  stop.
- **Presidio scrubbing**: applied as a second layer to anything that is
  logged, or that does travel to a cloud LLM tier for non-employee
  queries — masks names, emails, ID numbers before they leave the network
  or hit a log store.
- **Audit logging**: every query, the chunks retrieved, the model actually
  used, and the final answer are logged with `tenant_id` and `user_id`,
  satisfying "who asked what, and what was it answered with" for any later
  compliance review.

## 4. Per-domain guardrail configuration (no code changes required)

Each tenant's `guardrail_policies` row is a declarative policy document,
evaluated by Guardrails AI / NeMo Guardrails at request time:

```json
{
  "refusal_topics": ["competitor pricing", "unrelated medical advice"],
  "required_disclaimer": "Consult a licensed physician for medical decisions.",
  "pii_fields_to_mask": ["employee_name", "employee_id", "salary"]
}
```

A Healthcare tenant's admin sets a strict medical-disclaimer policy; a
Retail/Clothing tenant's admin might set none at all — both are the same
code path reading a different config row, exactly matching the "onboarding
a new domain requires configuration only" requirement from Module 1.

## 5. Network security

- All internal service-to-service traffic stays inside the cluster network
  — only the gateway is internet-facing.
- TLS terminated at the gateway/ingress; internal traffic can run over the
  cluster's service mesh encryption if the platform adopts one (optional
  for the initial build, worth revisiting once tenant count grows).
- Rate limiting at the gateway per tenant, so one tenant's traffic spike
  (or a misbehaving script) can't degrade another tenant's experience.
