from fastapi import APIRouter
from rag_platform_schemas.common import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    # In a real implementation this would aggregate downstream health
    return HealthResponse(
        status="ok",
        service="gateway",
        checks={}
    )
