import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import TenantDB
from app.infrastructure.database import get_db_session
from rag_platform_schemas.auth import Tenant, TenantCreate
from app.config import settings

router = APIRouter()

@router.post("", response_model=Tenant, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreate,
    setup_token: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new tenant (platform admin / setup only)."""
    if setup_token != settings.setup_token:
        raise HTTPException(status_code=403, detail="Invalid setup token")
        
    existing = await db.scalar(select(TenantDB).where(TenantDB.domain == req.domain))
    if existing:
        raise HTTPException(status_code=409, detail="Tenant with domain already exists")
        
    tenant = TenantDB(name=req.name, domain=req.domain)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    
    return tenant
