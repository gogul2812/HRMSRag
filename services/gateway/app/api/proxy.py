import httpx
from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse

async def forward_request(request: Request, target_url: str) -> Response:
    """
    Generic reverse proxy handler using httpx.
    """
    client = request.app.state.http_client
    
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))
    
    # We forward all headers except host
    headers = dict(request.headers)
    headers.pop("host", None)
    
    # Send request
    req = client.build_request(
        request.method,
        f"{target_url}{url}",
        headers=headers,
        content=request.stream()
    )
    
    try:
        res = await client.send(req, stream=True)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Bad Gateway: {str(exc)}")
        
    return StreamingResponse(
        res.aiter_raw(),
        status_code=res.status_code,
        headers={k: v for k, v in res.headers.items() if k.lower() != "transfer-encoding"},
        background=res.aclose
    )
