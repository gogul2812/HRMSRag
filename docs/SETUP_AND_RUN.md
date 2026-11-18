# Setup and Run Guide - New Machine Checklist

Follow these steps **in order** on every new PC.

---

## Critical: correct folder

Zip layouts often look like:

```text
rag-platform-new\          <-- WRONG (parent)
  rag-platform\            <-- CORRECT (run scripts here)
    docker-compose.dev.yml
    requirements.txt
    scripts\
```

Always:

```powershell
cd C:\path\to\rag-platform
dir docker-compose.dev.yml
```

If that file is missing, you are in the wrong folder.

---

## 0) Install first

| Tool | Version |
|------|---------|
| Docker Desktop | 24+ (must be Running) |
| Python | 3.11 or 3.12 (Add to PATH) |
| Node.js | 20 LTS |

Open a **new** PowerShell after installing.

---

## 1) One-time setup

```powershell
cd C:\path\to\rag-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_local.ps1
```

This creates `.venv`, installs `requirements.txt`, runs `npm install`, creates a clean UTF-8 `.env`, starts Docker, and runs migrations.

---

## 2) Edit `.env`

Set real values (no quotes around keys):

```env
POSTGRES_PASSWORD=YourStrongDbPassword
REDIS_PASSWORD=YourStrongRedisPassword
JWT_SECRET_KEY=any_long_random_string
SETUP_TOKEN=local-setup-token
GROQ_API_KEY=gsk_your_real_key
```

If you changed DB/Redis passwords **after** containers already existed:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml down -v
.\scripts\setup_local.ps1
```

---

## 3) Start every day

```powershell
cd C:\path\to\rag-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_local.ps1
```

| App | URL |
|-----|-----|
| Admin | http://localhost:3000 |
| User | http://localhost:3001 |
| Health | http://localhost:8000/health |

Stop APIs: `.\scripts\stop_local.ps1`

---

## 4) Create Super Admin, Org Admin, and User (full process)

You need **three roles** for a client demo. Easiest path = script. Manual UI path is below that.

### Option A — one script (recommended on client laptop)

With the stack already running (`start_local.ps1` OK):

```powershell
.\scripts\bootstrap_demo.ps1
```

That creates:

| Role | Portal | How to login | Email / password |
|------|--------|--------------|------------------|
| **Super Admin** | http://localhost:3000 | Tick **Platform Super Admin** (no org dropdown) | `superadmin@example.com` / `StrongPassword123!` |
| **Org Admin** | http://localhost:3000 | Untick Super Admin → pick **Demo Corp** | `admin@example.com` / `StrongPassword123!` |
| **End User** | http://localhost:3001 | Pick **Demo Corp** | `user@example.com` / `StrongPassword123!` |

### Option B — create accounts yourself (good for live client walkthrough)

**Step 1 — Super Admin (once per empty database)**

PowerShell (while stack is up). `SETUP_TOKEN` must match `.env` (default `local-setup-token`):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/organizations/bootstrap-super-admin `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Platform Super Admin\",\"email\":\"superadmin@example.com\",\"password\":\"StrongPassword123!\"}"
```

Then open Admin portal → tick **Platform Super Admin** → login with that email/password.

**Step 2 — Organization + Org Admin (as Super Admin in UI)**

1. Login as Super Admin  
2. Go to **Organizations**  
3. Create organization (e.g. name `Demo Corp`) and set first admin email/password when the form asks  
4. Sign out  

**Step 3 — more users as Org Admin**

1. Login Admin portal → pick **Demo Corp** → Org Admin credentials  
2. Go to **Users**  
3. Create user: name, email, password, role `User` (end_user) or `Admin`  

**Step 4 — User portal login**

1. Open http://localhost:3001  
2. Pick organization **Demo Corp**  
3. Login with the end-user email/password  

**Alternate:** User can also **Register** on the user portal (same org dropdown) — that always creates an `end_user`.

### What each role shows in the demo

| Role | Show the client |
|------|-----------------|
| Super Admin | Create/disable orgs; manage users across orgs; Profile |
| Org Admin | Upload docs, Rules, Guardrails, Users, Profile, View documents |
| End User | Chat, Compare, History, Profile (answers from that org’s docs only) |

---

## 5) Test RAG

1. Admin -> Documents -> upload `samples\demo\*`
2. Wait until status is **Indexed** (not Pending)
3. User -> Chat -> ask about leave days

If chat says **INSUFFICIENT INFORMATION** and docs are still **Pending**, indexing did not run. Restart with `.\scripts\start_local.ps1` (forces in-process Celery), delete Pending docs, upload again.

---

## Troubleshooting (known issues)

### Wrong folder
Symptom: script cannot find `docker-compose.dev.yml` or `requirements.txt`.  
Fix: `cd` into the **inner** `rag-platform` folder.

### Corrupted `.env` encoding
Symptom: garbled characters like `A~` / `Ã` on line 1-2; scripts break.  
Fix:

```powershell
del .env
.\scripts\setup_local.ps1
```

(setup recreates UTF-8 without BOM)

### Windows `DEBUG=release` crash
Symptom: auth-service ValidationError on `debug` bool.  
Fix: already applied in code (`app_debug`). Scripts also unset `DEBUG`. Use `APP_DEBUG=true` in `.env`, never rely on system `DEBUG`.

### litellm needs Rust
Symptom: pip build fails compiling litellm.  
Fix: `requirements.txt` pins `litellm>=1.40.0,<1.92.0` and setup uses `--prefer-binary`.

### Documents stuck on Pending
Cause: no Celery worker and eager mode off.  
Fix: `start_local.ps1` always sets `CELERY_TASK_ALWAYS_EAGER=1`. Restart stack, re-upload docs.

### Qdrant shows unhealthy
Old healthcheck used `curl` (not in image). Compose now uses a TCP probe. Recreate:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d --force-recreate qdrant
```

Qdrant can still serve on :6333 even if health was flaky; check `http://127.0.0.1:6333/readyz`.

### `.venv` in wrong place
Must be `rag-platform\.venv`, not the parent folder. Delete the wrong venv and re-run setup.

### Cline / Groq `reasoning_details` error
That error is from the **Cline IDE extension**, not from this RAG app. Ignore it for project startup. Use Cursor/terminal scripts above.

---

## Ports

| Service | Host port |
|---------|-----------|
| Postgres | 15432 |
| Redis | 16379 |
| Qdrant | 6333 |
| Gateway | 8000 |
| APIs | 8001-8006 |
| Admin UI | 3000 |
| User UI | 3001 |

---

## Logs

```text
logs\local\*.err.log
docker logs ragplatform_postgres --tail 50
docker logs ragplatform_qdrant --tail 50
```

---

## Related docs

- `README.md` - short quick start
- `PROJECT_KNOWLEDGE_BASE.md` - full product reference
- `API_KEYS.md` - Groq keys
