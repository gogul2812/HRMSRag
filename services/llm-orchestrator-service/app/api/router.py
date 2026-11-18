from fastapi import APIRouter

from app.api.v1 import orchestrate

api_router = APIRouter()
api_router.include_router(orchestrate.router, prefix="/orchestrate", tags=["orchestrate"])
