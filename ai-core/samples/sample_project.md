# Acme Healthcare — Project Phoenix

## Overview

Project Phoenix is an internal staffing feasibility study for a hospital
network EHR migration. This document captures the tech stack, team
composition, and open risks.

## Tech Stack

- Backend: FastAPI, Python 3.11
- Database: PostgreSQL 16 with row-level security
- Vector store: Qdrant (self-hosted)
- Embedding: BGE-large-en-v1.5

## Team Roster

| Employee | Role | Years | Specialty |
|---|---|---|---|
| Ava Chen | Lead Engineer | 8 | HL7 / FHIR |
| Marcus Lee | Data Engineer | 5 | ETL / Postgres |
| Priya Nair | QA Lead | 6 | Clinical workflows |

## Risks

### Data residency

Employee and patient-adjacent metadata must remain on-network. Cloud LLM
providers are only used when retrieved context excludes `doc_type: employee`.

### Timeline

Target go-live is Q4. Parallel ingestion of 100+ project markdown files is
required without degrading live chat latency.
