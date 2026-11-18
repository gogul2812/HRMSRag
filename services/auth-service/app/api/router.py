from fastapi import APIRouter
from app.api.v1 import auth, tenants, organizations

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(
    organizations.router, prefix="/organizations", tags=["organizations"]
)
