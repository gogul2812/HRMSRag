# API keys — what to paste into `.env`

Open `rag-platform/.env` in an editor. Replace the `CHANGE_ME` values below.
**Do not commit `.env`.**

---

## 1) Required to chat with a real model — Groq (primary)

1. Go to: https://console.groq.com/keys  
2. Sign up / log in  
3. Click **Create API Key** → copy it  
4. In `.env` set:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_ROUTER_MODE=litellm
CHAT_FAKE_ORCHESTRATOR=0
```

Default model (already set): `groq/llama-3.3-70b-versatile`

---

## 2) Optional fallbacks (recommended)

### Google Gemini
1. https://aistudio.google.com/apikey  
2. Create API key → paste:

```env
GEMINI_API_KEY=AIza...
```

### OpenRouter
1. https://openrouter.ai/keys  
2. Create key → paste:

```env
OPENROUTER_API_KEY=sk-or-v1-...
```

Fallback order: **Groq → Gemini → OpenRouter → local Ollama** (if running).

---

## 3) Already configured for local Docker (usually leave alone)

| Variable | Purpose |
|---|---|
| `POSTGRES_*` / `DATABASE_URL*` | DB (host port **15432** on this machine) |
| `REDIS_*` | Redis (host port **16379** on this machine) |
| `JWT_SECRET_KEY` | Auth tokens |
| `SETUP_TOKEN` | Bootstrap tenant/admin (`local-setup-token`) |

---

## 4) After pasting keys

```powershell
cd "rag-platform"
.\scripts\start_local.ps1
```

Then open:
- Admin portal: http://localhost:3000  
- User portal: http://localhost:3001  
- API gateway: http://localhost:8000/health  

First-time admin bootstrap (if no users yet):

```powershell
# Create tenant
curl -X POST http://localhost:8001/api/v1/tenants `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"My Org\",\"domain\":\"my-org\"}"

# Register admin (use tenant id from previous response)
curl -X POST http://localhost:8001/api/v1/auth/register-admin `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"admin@example.com\",\"password\":\"StrongPassword123!\",\"tenant_id\":\"PASTE_TENANT_ID\",\"role\":\"admin\"}"
```

Log in on the portals with that email/password.
