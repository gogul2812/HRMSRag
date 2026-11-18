# infra/terraform

**Technology:** Terraform (HashiCorp)

## Purpose

This directory contains Terraform modules for provisioning cloud infrastructure.

### Structure (planned — Stage 12)

```
terraform/
├── modules/
│   ├── postgres/     # Managed Postgres (RDS / Cloud SQL)
│   ├── redis/        # Managed Redis (ElastiCache / Memorystore)
│   ├── k8s-cluster/  # Kubernetes cluster (EKS / GKE / AKS)
│   ├── object-storage/ # S3 bucket / Cloudflare R2
│   └── dns/          # DNS records for admin.* and app.*
├── environments/
│   ├── staging/
│   └── production/
└── README.md
```

### Design principles

- All sensitive values (DB passwords, API keys) are stored in the cloud
  provider's secrets manager — never in Terraform state as plaintext.
- Terraform state is stored remotely (S3 + DynamoDB lock, or Terraform Cloud).
- `terraform plan` is run in CI on every PR; `terraform apply` requires manual
  approval in the production environment.

## Implementation module

Module 6 — `06-infra-and-devops-module.md`
