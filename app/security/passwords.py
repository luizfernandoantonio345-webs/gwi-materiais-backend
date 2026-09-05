import re

import bcrypt
from fastapi import HTTPException, status

_REGRAS = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{12,}$")


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def conferir_senha(senha: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hashed.encode())
    except ValueError:
        return False


def validar_forca(senha: str) -> None:
    if not _REGRAS.match(senha):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Senha fraca: mínimo 12 caracteres com maiúscula, minúscula, número e símbolo.",
        )
