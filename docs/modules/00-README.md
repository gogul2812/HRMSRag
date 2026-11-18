# RAG Chatbot Platform — Module Documentation

This documentation set breaks the platform into independent modules. Each
module is a standalone `.md` file so it can be assigned, reviewed, and built
separately by different engineers, while Module 1 stays the shared source of
truth for structure and stack decisions that every other module depends on.

## Reading order

| # | File | Purpose |
|---|---|---|
| 1 | `01-requirements-and-project-structure.md` | **Start here.** Full requirements, repo/folder structure, complete tech stack, multi-tenant design principle |
| 2 | `02-frontend-module.md` | Admin Portal + User Portal — pages, components, state, streaming chat UI |
| 3 | `03-backend-microservices-module.md` | Every microservice, its responsibility, its API contract, and how they talk to each other |
| 4 | `04-ai-pipeline-module.md` | Parsing → chunking → embedding → vector storage → retrieval → rerank → LLM router, with the exact model/tool at each stage |
| 5 | `05-data-and-multitenancy-module.md` | Database schema, per-tenant isolation strategy, vector DB tagging |
| 6 | `06-infra-and-devops-module.md` | Containers, orchestration, CI/CD, environments, scaling path |
| 7 | `07-security-and-guardrails-module.md` | AuthN/AuthZ, secrets, PII handling, guardrail policy engine, compliance per domain |
| 8 | `08-testing-and-evaluation-module.md` | Unit/integration testing per service, RAG-specific evaluation (RAGAS), load testing |
| 9 | `09-implementation-roadmap-module.md` | Build order, milestones, definition of done per module |

## Core design principle (applies to every module below)

This is a **multi-tenant, multi-domain** platform from day one. The same
deployment will serve multiple internal teams and domains (e.g. Healthcare
project docs, Clothing/Retail project docs, HR/HRMS-style employee data,
and any future domain) without forking the codebase. Every module is written
with that constraint in mind: **nothing domain-specific is allowed to live
in code — it lives in per-tenant configuration** (uploaded documents, active
prompt/rules configuration, guardrail policy). This is what makes the
platform production-grade rather than a single-purpose script.
