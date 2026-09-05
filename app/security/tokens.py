import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.base import garantir_aware
from ..models.seguranca import RefreshToken
from ..models.usuario import Usuario

settings = get_settings()


def _agora() -> datetime:
    return datetime.now(UTC)


def criar_access_token(usuario: Usuario, mfa_ok: bool) -> str:
    payload = {
        "sub": str(usuario.id),
        "papel": usuario.papel.value,
        "tenant": usuario.tenant,
        "mfa": mfa_ok,
        "type": "access",
        "exp": _agora() + timedelta(minutes=settings.access_token_ttl_min),
        "iat": _agora(),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def emitir_refresh_token(db: AsyncSession, usuario: Usuario) -> str:
    jti = uuid.uuid4().hex
    expira = _agora() + timedelta(days=settings.refresh_token_ttl_days)
    db.add(RefreshToken(jti=jti, usuario_id=usuario.id, expira_em=expira))
    payload = {"sub": str(usuario.id), "type": "refresh", "jti": jti, "exp": expira, "iat": _agora()}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decodificar(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


async def rotacionar_refresh(db: AsyncSession, token: str) -> tuple[str, str] | None:
    try:
        payload = decodificar(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "refresh":
        return None
    jti = payload.get("jti")
    res = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    registro = res.scalar_one_or_none()
    if not registro or registro.revogado or garantir_aware(registro.expira_em) < _agora():
        if registro and registro.revogado:
            await _revogar_cadeia(db, registro.usuario_id)
        return None
    usuario = await db.get(Usuario, registro.usuario_id)
    if not usuario or not usuario.ativo:
        return None
    novo_refresh = await emitir_refresh_token(db, usuario)
    registro.revogado = True
    registro.substituido_por = decodificar(novo_refresh)["jti"]
    novo_access = criar_access_token(usuario, mfa_ok=True)
    return novo_access, novo_refresh


async def revogar(db: AsyncSession, jti: str) -> None:
    res = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    reg = res.scalar_one_or_none()
    if reg:
        reg.revogado = True


async def _revogar_cadeia(db: AsyncSession, usuario_id: int) -> None:
    res = await db.execute(select(RefreshToken).where(RefreshToken.usuario_id == usuario_id, RefreshToken.revogado == False))  # noqa: E712
    for reg in res.scalars().all():
        reg.revogado = True
