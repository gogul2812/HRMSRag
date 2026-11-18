from fastapi import APIRouter

from app.api.v1 import ingest

api_router = APIRouter()
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
