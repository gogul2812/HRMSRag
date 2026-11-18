from fastapi import APIRouter

from app.api.v1 import retrieve

api_router = APIRouter()
api_router.include_router(retrieve.router, prefix="/retrieve", tags=["retrieve"])
