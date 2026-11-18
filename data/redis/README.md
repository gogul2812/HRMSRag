# data/redis

**Technology:** Redis 7, Celery

## Purpose

This directory contains configuration and documentation for the Redis instance
used as:

1. **Celery broker and result backend** — ingestion jobs are enqueued here
   and Celery workers pull tasks from this queue.
2. **JWT deny-list** — revoked tokens are stored with a TTL matching their
   remaining expiry time; the Auth Service checks this on every token refresh
   and the Gateway checks it on every request (using a local cache to minimise
   round trips).
3. **Pub/Sub for ingestion events** — the Celery worker publishes status
   changes (`pending → processing → indexed / failed`) to a Redis channel
   that the Notification Service subscribes to.
4. **Rate-limit counters** — the Gateway uses Redis atomic increments for
   per-tenant rate limiting.

### Cache key naming convention

All keys are namespaced to prevent collisions:

```
ragplatform:{tenant_id}:jwt_deny:{jti}              TTL = token remaining expiry
ragplatform:{tenant_id}:ratelimit:{user_id}:{window}
ragplatform:celery:*                                  (Celery managed)
ragplatform:pubsub:ingestion:{tenant_id}              (channel name)
```

### Configuration

Redis is configured via command-line flags in `docker-compose.dev.yml`:
- Persistence: AOF (`appendonly yes`, `appendfsync everysec`)
- Password: required (set via `REDIS_PASSWORD` in `.env`)

Production Redis configuration (cluster mode, TLS) is defined in `infra/k8s/`.
