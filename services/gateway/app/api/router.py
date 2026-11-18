from fastapi import APIRouter

from app.config import settings
from app.routes import auth_routes, stub_routes
from app.routes.service_proxy import make_proxy_router

router = APIRouter()

# Auth + organizations (same auth-service)
router.include_router(auth_routes.router, prefix="/auth")
router.include_router(auth_routes.router, prefix="/tenants")
router.include_router(auth_routes.router, prefix="/organizations")

# Stage 2 + 4 — live proxies for Admin Portal (Stage 8)
router.include_router(
    make_proxy_router(lambda: settings.admin_config_service_url),
    prefix="/config",
)
router.include_router(
    make_proxy_router(lambda: settings.ingestion_service_url),
    prefix="/ingest",
)

# Stage 5–7 proxies (needed by User Portal / rules preview)
router.include_router(
    make_proxy_router(lambda: settings.retrieval_service_url),
    prefix="/retrieve",
)
router.include_router(
    make_proxy_router(lambda: settings.llm_orchestrator_service_url),
    prefix="/orchestrate",
)
router.include_router(
    make_proxy_router(lambda: settings.chat_service_url),
    prefix="/chat",
)

# Still stubbed
router.include_router(stub_routes.router, prefix="/admin")
router.include_router(stub_routes.router, prefix="/notify")
