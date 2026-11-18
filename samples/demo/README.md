# How to test the RAG demo

## Login (same for both portals)

| Field | Value |
|---|---|
| **Tenant ID** | `9737633b-a683-4af0-81fb-8a4216caea0d` |
| **Password** | `StrongPassword123!` |

- **Admin:** http://localhost:3000 → email `admin@example.com`
- **User:** http://localhost:3001 → email `user@example.com`

## Files to upload (Admin → Documents)

Upload these three files from this folder:

1. `01-leave-policy.md`
2. `02-wfh-policy.md`
3. `03-project-phoenix.md`

Wait until each shows status **indexed** (refresh if needed).

## Questions to ask (User → Chat)

Try these after indexing:

1. How many annual leave days do employees get?
2. Can unused leave be carried forward? How many days?
3. What are the default WFH days?
4. What are core hours when working from home?
5. Which hospitals are in the Project Phoenix pilot?
6. Who approves change requests over 40 hours on Project Phoenix?

You should see answers grounded in the uploaded docs (and citations when the UI shows them).
