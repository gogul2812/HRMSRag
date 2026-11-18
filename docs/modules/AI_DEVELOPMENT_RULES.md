# AI Development Rules

You are building an enterprise, multi-tenant HRMS RAG platform.

The architecture defined in the numbered module files (00–09) is finalized.
Do not redesign it, question it, or propose alternatives unless explicitly
asked to.

## Hard rules

- Never rename folders.
- Never rename services.
- Never introduce a technology not named in `01-requirements-and-project-structure.md`.
- Never change the folder structure defined in Module 1.
- Never remove existing code unless explicitly instructed.
- Never hardcode configuration — anything environment- or tenant-specific
  belongs in `.env` files or database config, never in source code.
- Never create a duplicate implementation of something that already exists
  in `ai-core/` or `shared-libs/` — import and reuse it instead.
- Never add tenant-specific logic as a code branch (e.g.
  `if tenant == "healthcare"`). Domain differences belong in
  `prompt_configs` / `guardrail_policies` data, not in code. If a task
  seems to need a per-tenant branch, stop and flag it instead of writing one.

## Always

- Follow SOLID principles.
- Follow Clean Architecture (clear separation between API/interface layer,
  business logic, and data access — no business logic inside route
  handlers).
- Every service must ship with:
  - `Dockerfile`
  - `README.md` explaining what the service does and how to run it
  - Unit tests
  - Structured logging (JSON, includes `tenant_id` and `request_id` where
    applicable)
  - Structured error handling (no bare `except:`, no silently swallowed
    errors)
  - OpenAPI documentation (FastAPI's auto-generated docs, kept accurate)
- Every module/stage you implement must match its corresponding numbered
  module file exactly. If something in a module file is ambiguous, ask
  before assuming.

## Stopping condition

- Implement only the stage you are explicitly asked to implement.
- Do not start the next stage, even partially, even if it seems like a
  natural continuation.
- Stop and summarize what was built, what was tested, and what the next
  stage would be — then wait for the next instruction.

## Reference

Full stage-by-stage build order and definition-of-done per stage:
`09-implementation-roadmap-module.md`.
