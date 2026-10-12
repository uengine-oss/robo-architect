"""PC upload/SSE transport to the server, with no local execution fallback."""
import os
from urllib.parse import urlsplit

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, StreamingResponse


def ingestion_url() -> str:
    raw = os.environ.get('ROBO_INGESTION_URL', '').strip().rstrip('/')
    if not raw:
        return ''
    value = urlsplit(raw)
    if (value.scheme not in ('https', 'http') or not value.hostname or value.username
            or value.password or value.path not in ('', '/') or value.query or value.fragment
            or (value.scheme == 'http' and value.hostname not in ('localhost', '127.0.0.1', '::1'))):
        raise ValueError('ROBO_INGESTION_URL은 HTTPS 서버 origin이어야 합니다.')
    return raw


class IngestionProxyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            origin = ingestion_url()
        except ValueError:
            return JSONResponse({'detail':'서버 ingestion 주소를 확인하세요.'}, status_code=503)
        path = request.url.path
        if not origin or not (path == '/api/ingest' or path.startswith('/api/ingest/')) or request.method == 'OPTIONS':
            return await call_next(request)
        headers = {key:request.headers[key] for key in ('authorization', 'x-project-graph',
                   'content-type', 'accept', 'accept-language', 'last-event-id') if key in request.headers}
        client = httpx.AsyncClient(timeout=httpx.Timeout(30, read=None), trust_env=False)
        try:
            message = client.build_request(request.method, origin + path,
                         params=list(request.query_params.multi_items()), headers=headers,
                         content=request.stream())
            upstream = await client.send(message, stream=True)
        except httpx.HTTPError:
            await client.aclose()
            return JSONResponse({'detail':'서버 ingestion에 연결할 수 없습니다.'}, status_code=503)
        async def body():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()
        return StreamingResponse(body(), status_code=upstream.status_code,
                                 headers={key:upstream.headers[key] for key in
                                 ('content-type', 'cache-control') if key in upstream.headers})
