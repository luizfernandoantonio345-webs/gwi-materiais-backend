import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import get_settings
from ..logging_conf import novo_request_id, request_id_ctx

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if "server" in response.headers:
            del response.headers["server"]
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or novo_request_id()
        request_id_ctx.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    def _limite(self, path: str) -> int:
        if path.startswith("/auth/login"):
            return settings.rate_limit_login_per_min
        return settings.rate_limit_per_min

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        chave = f"{ip}:{'login' if request.url.path.startswith('/auth/login') else 'geral'}"
        agora = time.monotonic()
        janela = self._hits[chave]
        while janela and agora - janela[0] > 60:
            janela.popleft()
        if len(janela) >= self._limite(request.url.path):
            return JSONResponse(status_code=429, content={"detail": "Muitas requisições. Tente novamente em instantes."})
        janela.append(agora)
        return await call_next(request)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST":
            return await call_next(request)
        chave = request.headers.get("Idempotency-Key")
        if not chave:
            return await call_next(request)

        from sqlalchemy import select

        from .. import database as _db
        from ..models.seguranca import IdempotencyKey

        endpoint = request.url.path
        async with _db.SessionLocal() as sessao:
            existe = await sessao.execute(select(IdempotencyKey).where(IdempotencyKey.chave == chave, IdempotencyKey.endpoint == endpoint))
            registro = existe.scalar_one_or_none()
            if registro:
                return JSONResponse(
                    status_code=registro.status_code,
                    content=__import__("json").loads(registro.resposta),
                    headers={"Idempotent-Replay": "true"},
                )

        response = await call_next(request)
        corpo = b""
        async for chunk in response.body_iterator:
            corpo += chunk

        if 200 <= response.status_code < 300:
            try:
                async with _db.SessionLocal() as sessao:
                    sessao.add(
                        IdempotencyKey(
                            chave=chave, usuario_id=0, endpoint=endpoint, status_code=response.status_code, resposta=corpo.decode() or "{}"
                        )
                    )
                    await sessao.commit()
            except Exception:
                pass

        return Response(content=corpo, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
