# Generate thin per-service GitHub Actions workflows.
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
CI = ROOT / "infra" / "ci-cd"
WF.mkdir(parents=True, exist_ok=True)
CI.mkdir(parents=True, exist_ok=True)

# name, path filter roots, service_path, dockerfile, context
SERVICES = [
    (
        "gateway",
        ["services/gateway/**", "infra/docker/Dockerfile.gateway", "shared-libs/**", "ai-core/**"],
        "services/gateway",
        "infra/docker/Dockerfile.gateway",
        ".",
    ),
    (
        "auth-service",
        ["services/auth-service/**", "infra/docker/Dockerfile.auth-service", "shared-libs/**"],
        "services/auth-service",
        "infra/docker/Dockerfile.auth-service",
        ".",
    ),
    (
        "admin-config-service",
        [
            "services/admin-config-service/**",
            "infra/docker/Dockerfile.admin-config-service",
            "shared-libs/**",
        ],
        "services/admin-config-service",
        "infra/docker/Dockerfile.admin-config-service",
        ".",
    ),
    (
        "ingestion-service",
        [
            "services/ingestion-service/**",
            "infra/docker/Dockerfile.ingestion-service",
            "shared-libs/**",
            "ai-core/**",
        ],
        "services/ingestion-service",
        "infra/docker/Dockerfile.ingestion-service",
        ".",
    ),
    (
        "retrieval-service",
        [
            "services/retrieval-service/**",
            "infra/docker/Dockerfile.retrieval-service",
            "shared-libs/**",
            "ai-core/**",
        ],
        "services/retrieval-service",
        "infra/docker/Dockerfile.retrieval-service",
        ".",
    ),
    (
        "llm-orchestrator-service",
        [
            "services/llm-orchestrator-service/**",
            "infra/docker/Dockerfile.llm-orchestrator-service",
            "shared-libs/**",
            "ai-core/**",
        ],
        "services/llm-orchestrator-service",
        "infra/docker/Dockerfile.llm-orchestrator-service",
        ".",
    ),
    (
        "chat-service",
        [
            "services/chat-service/**",
            "infra/docker/Dockerfile.chat-service",
            "shared-libs/**",
            "ai-core/**",
        ],
        "services/chat-service",
        "infra/docker/Dockerfile.chat-service",
        ".",
    ),
]

TEMPLATE = """name: CI — {name}

on:
  push:
    branches: [main]
    paths:
{paths}
  pull_request:
    branches: [main]
    paths:
{paths}
  workflow_dispatch:

jobs:
  ci:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: {name}
      service_path: {service_path}
      dockerfile: {dockerfile}
      context: "{context}"
{extra_with}
    secrets: inherit
"""


def fmt_paths(paths: list[str]) -> str:
    return "\n".join(f"      - {p}" for p in paths)


def main() -> None:
    for name, paths, service_path, dockerfile, context in SERVICES:
        extra = (
            '      extra_rollouts: ingestion-worker\n'
            if name == "ingestion-service"
            else ""
        )
        body = TEMPLATE.format(
            name=name,
            paths=fmt_paths(paths),
            service_path=service_path,
            dockerfile=dockerfile,
            context=context,
            extra_with=extra,
        )
        (WF / f"{name}.yml").write_text(body, encoding="utf-8")
        (CI / f"{name}.yml").write_text(
            f"# Source of truth: .github/workflows/{name}.yml\n"
            f"# GitHub Actions only loads workflows from .github/workflows/.\n"
            f"# This file is kept for Module 6 layout parity.\n\n" + body,
            encoding="utf-8",
        )
        print("wrote", name)

    # shared-libs: rebuild dependents
    shared = """name: CI — shared-libs

on:
  push:
    branches: [main]
    paths:
      - "shared-libs/**"
      - "ai-core/**"
      - ".github/workflows/shared-libs.yml"
  pull_request:
    branches: [main]
    paths:
      - "shared-libs/**"
      - "ai-core/**"
  workflow_dispatch:

jobs:
  gateway:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: gateway
      service_path: services/gateway
      dockerfile: infra/docker/Dockerfile.gateway
      context: "."
    secrets: inherit
  auth-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: auth-service
      service_path: services/auth-service
      dockerfile: infra/docker/Dockerfile.auth-service
      context: "."
    secrets: inherit
  admin-config-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: admin-config-service
      service_path: services/admin-config-service
      dockerfile: infra/docker/Dockerfile.admin-config-service
      context: "."
    secrets: inherit
  ingestion-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: ingestion-service
      service_path: services/ingestion-service
      dockerfile: infra/docker/Dockerfile.ingestion-service
      context: "."
    secrets: inherit
  retrieval-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: retrieval-service
      service_path: services/retrieval-service
      dockerfile: infra/docker/Dockerfile.retrieval-service
      context: "."
    secrets: inherit
  llm-orchestrator-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: llm-orchestrator-service
      service_path: services/llm-orchestrator-service
      dockerfile: infra/docker/Dockerfile.llm-orchestrator-service
      context: "."
    secrets: inherit
  chat-service:
    uses: ./.github/workflows/reusable-service-ci.yml
    with:
      service_name: chat-service
      service_path: services/chat-service
      dockerfile: infra/docker/Dockerfile.chat-service
      context: "."
    secrets: inherit
"""
    (WF / "shared-libs.yml").write_text(shared, encoding="utf-8")
    (CI / "shared-libs.yml").write_text(
        "# Source of truth: .github/workflows/shared-libs.yml\n\n" + shared,
        encoding="utf-8",
    )
    print("wrote shared-libs")

    frontend = """name: CI — frontend

on:
  push:
    branches: [main]
    paths:
      - "frontend/**"
      - ".github/workflows/frontend.yml"
  pull_request:
    branches: [main]
    paths:
      - "frontend/**"
  workflow_dispatch:

jobs:
  lint-build:
    name: Lint & build portals
    runs-on: ubuntu-latest
    strategy:
      matrix:
        app: [admin-portal, user-portal]
    defaults:
      run:
        working-directory: frontend/${{ matrix.app }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/${{ matrix.app }}/package-lock.json
      - name: Install
        run: npm ci || npm install
      - name: Lint
        run: npm run lint --if-present
      - name: Build
        run: npm run build
        env:
          NEXT_PUBLIC_API_BASE_URL: https://staging-api.rag-platform.example

  deploy-staging:
    name: Deploy staging (portals)
    needs: lint-build
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Placeholder deploy
        run: |
          echo "Build artifacts from lint-build; wire Vercel/S3/k8s Ingress here."
          echo "Admin portal → staging-admin.rag-platform.example"
          echo "User portal  → staging-app.rag-platform.example"

  deploy-production:
    name: Deploy production (portals)
    needs: deploy-staging
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Placeholder deploy
        run: |
          echo "Manual approval required via GitHub Environment 'production'."
          echo "Admin portal → admin.rag-platform.example"
          echo "User portal  → app.rag-platform.example"
"""
    (WF / "frontend.yml").write_text(frontend, encoding="utf-8")
    (CI / "frontend.yml").write_text(
        "# Source of truth: .github/workflows/frontend.yml\n\n" + frontend,
        encoding="utf-8",
    )
    print("wrote frontend")


if __name__ == "__main__":
    main()
