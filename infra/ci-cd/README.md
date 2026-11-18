# infra/ci-cd

**Technology:** GitHub Actions

## Purpose

One pipeline per independently deployable unit: **lint → test → build → push →
auto-deploy staging → manual-approval production**.

## Where files live

GitHub only executes workflows under **`.github/workflows/`**.  
Copies (or generators) under `infra/ci-cd/` match Module 6 naming and stay in
sync via `infra/ci-cd/_gen_workflows.py`.

| Workflow | Triggers on |
|---|---|
| `gateway.yml` | `services/gateway/**`, Dockerfile, shared-libs |
| `auth-service.yml` | `services/auth-service/**` … |
| `admin-config-service.yml` | … |
| `ingestion-service.yml` | … (+ rebuilds worker image) |
| `retrieval-service.yml` | … |
| `llm-orchestrator-service.yml` | … |
| `chat-service.yml` | … |
| `shared-libs.yml` | `shared-libs/**`, `ai-core/**` → rebuilds all dependents |
| `frontend.yml` | `frontend/**` (admin-portal + user-portal) |
| `reusable-service-ci.yml` | called by the above |

## Pipeline stages (backend)

1. **Lint** — `ruff check` + `ruff format --check`
2. **Unit tests** — `pytest` when `tests/` exists
3. **Build / push** — Docker image to GHCR tagged with commit SHA
4. **Deploy staging** — `kubectl apply -k infra/k8s/overlays/staging` on `main`
5. **Deploy production** — same for production overlay; gated by GitHub
   Environment **`production`** (require reviewers)

## Setup checklist

1. Create GitHub Environments: `staging`, `production` (production: required reviewers).
2. Add secrets `KUBE_CONFIG_STAGING` / `KUBE_CONFIG_PRODUCTION` (base64 kubeconfig).
3. Enable GHCR packages for the repository.
4. Regenerate thin workflows after adding a service:  
   `python infra/ci-cd/_gen_workflows.py`

## Implementation module

Module 6 — `06-infra-and-devops-module.md`  
Stage 12 — `09-implementation-roadmap-module.md`
