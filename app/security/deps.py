from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.usuario import Papel, Usuario
from .tokens import decodificar

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)

_CRED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_usuario_atual(
    token: Annotated[str, Depends(oauth2)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Usuario:
    try:
        payload = decodificar(token)
    except jwt.PyJWTError:
        raise _CRED from None
    if payload.get("type") != "access":
        raise _CRED
    if not payload.get("mfa", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA pendente.")
    uid = payload.get("sub")
    if not uid:
        raise _CRED
    usuario = await db.get(Usuario, int(uid))
    if not usuario or not usuario.ativo:
        raise _CRED
    return usuario


CurrentUser = Annotated[Usuario, Depends(get_usuario_atual)]


def require_roles(*papeis: Papel):
    async def _dep(usuario: CurrentUser) -> Usuario:
        if usuario.papel not in papeis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")
        return usuario

    return _dep
