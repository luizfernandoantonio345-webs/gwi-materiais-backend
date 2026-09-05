from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_conf import logger, request_id_ctx


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id_ctx.get()},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validacao_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Dados inválidos.", "request_id": request_id_ctx.get()})

    @app.exception_handler(Exception)
    async def geral_handler(request: Request, exc: Exception):
        logger.exception("erro_nao_tratado")
        return JSONResponse(status_code=500, content={"detail": "Erro interno.", "request_id": request_id_ctx.get()})
