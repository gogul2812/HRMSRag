import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.retrieval_service import retrieve
from rag_platform_auth_middleware import require_role
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import JWTClaims, UserRole
from rag_platform_schemas.retrieval import RetrieveRequest, RetrieveResponse

router = APIRouter()
logger = get_logger(__name__)

# End users (User Portal) and admins may retrieve within their tenant.
CallerClaims = Annotated[JWTClaims, Depends(require_role(UserRole.END_USER))]


@router.post(
    "/query",
    response_model=RetrieveResponse,
    summary="Hybrid search + rerank, tenant-scoped",
)
async def query_retrieve(
    req: RetrieveRequest, claims: CallerClaims
) -> RetrieveResponse:
    tenant_id = str(claims.tenant_id)
    result = retrieve(tenant_id=tenant_id, req=req)
    logger.info(
        "retrieve_query",
        tenant_id=tenant_id,
        query=req.query[:120],
        hits=len(result.chunks),
        insufficient=result.insufficient_information,
        best_score=result.best_score,
    )
    return result
