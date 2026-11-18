# infra/k8s

**Technology:** Kubernetes + Kustomize

## Purpose

Production-oriented manifests for the RAG platform. Staging can use the same
base with a lighter overlay, or Docker Compose on a single VM
(`infra/docker-compose/staging.yml`).

## Layout

```
k8s/
├── base/                         # Shared manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.example.yaml      # Template only — do not apply as-is
│   ├── ingress.yaml              # External entry → gateway only
│   ├── postgres/                 # StatefulSet (staging / POC)
│   ├── redis/
│   ├── qdrant/
│   ├── gateway/
│   ├── auth-service/
│   ├── admin-config-service/
│   ├── ingestion-service/        # API Deployment + Service + HPA
│   ├── ingestion-worker/         # Separate Celery Deployment + HPA
│   ├── retrieval-service/
│   ├── llm-orchestrator-service/
│   └── chat-service/
├── overlays/
│   ├── staging/                  # 1 replica, fake models, staging host
│   └── production/               # Higher replicas, real models, TLS, no in-cluster Postgres
└── ENVIRONMENTS.md               # local / staging / production runbook
```

## Apply

```bash
kubectl apply -k infra/k8s/overlays/staging
kubectl apply -k infra/k8s/overlays/production
```

## Design notes

- One Deployment + Service (+ HPA) per microservice; ingestion API and Celery
  worker scale independently.
- Ingress is the only external HTTP path; all other Services are ClusterIP.
- Secrets: copy `secrets.example.yaml` → sealed-secrets / External Secrets /
  CI-injected Secret named `rag-platform-secrets`.
- Notification-service is not implemented yet; omit from base until Stage N/A.

## Implementation module

Module 6 — `06-infra-and-devops-module.md`  
Stage 12 — `09-implementation-roadmap-module.md`
