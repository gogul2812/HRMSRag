from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def stub_proxy(path: str):
    raise HTTPException(status_code=501, detail="Not Implemented in Stage 1")
