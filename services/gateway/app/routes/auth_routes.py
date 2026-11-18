from fastapi import APIRouter, Request
from app.api.proxy import forward_request
from app.config import settings

router = APIRouter()


async def _proxy(request: Request):
    return await forward_request(request, settings.auth_service_url)


# Empty path (e.g. POST /api/v1/organizations) must be explicit —
# /{path:path} does not match zero remaining segments.
@router.api_route("", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def auth_proxy_root(request: Request):
    return await _proxy(request)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def auth_proxy(request: Request, path: str):
    return await _proxy(request)
