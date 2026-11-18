# docs/modules

This directory contains the complete module specification for the RAG Platform.

## Reading order

| # | File | Purpose |
|---|---|---|
| 1 | [`01-requirements-and-project-structure.md`](01-requirements-and-project-structure.md) | **Start here.** Full requirements, repo/folder structure, complete tech stack, multi-tenant design principle |
| 2 | [`02-frontend-module.md`](02-frontend-module.md) | Admin Portal + User Portal — pages, components, state, streaming chat UI |
| 3 | [`03-backend-microservices-module.md`](03-backend-microservices-module.md) | Every microservice, its responsibility, its API contract, and how they talk to each other |
| 4 | [`04-ai-pipeline-module.md`](04-ai-pipeline-module.md) | Parsing → chunking → embedding → vector storage → retrieval → rerank → LLM router |
| 5 | [`05-data-and-multitenancy-module.md`](05-data-and-multitenancy-module.md) | Database schema, per-tenant isolation strategy, vector DB tagging |
| 6 | [`06-infra-and-devops-module.md`](06-infra-and-devops-module.md) | Containers, orchestration, CI/CD, environments, scaling path |
| 7 | [`07-security-and-guardrails-module.md`](07-security-and-guardrails-module.md) | AuthN/AuthZ, secrets, PII handling, guardrail policy engine |
| 8 | [`08-testing-and-evaluation-module.md`](08-testing-and-evaluation-module.md) | Unit/integration testing per service, RAGAS evaluation, load testing |
| 9 | [`09-implementation-roadmap-module.md`](09-implementation-roadmap-module.md) | Build order, milestones, definition of done per stage |

These files are the **source of truth** for all architectural decisions.
No service, folder name, or technology may be changed without updating the
relevant module file and getting explicit team approval.
