"""Proxy routes that forward to a downstream microservice."""

from fastapi import APIRouter, Request

from app.api.proxy import forward_request


def make_proxy_router(target_url_getter) -> APIRouter:
    router = APIRouter()

    @router.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def proxy(request: Request, path: str):
        return await forward_request(request, target_url_getter())

    return router
