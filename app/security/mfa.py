import secrets

import pyotp


def gerar_secret() -> str:
    return pyotp.random_base32()


def gerar_backup_codes(n: int = 8) -> list[str]:
    return [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(n)]


def uri_provisionamento(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="GWI Materiais")


def verificar_codigo(secret: str, codigo: str) -> bool:
    if not secret or not codigo:
        return False
    return pyotp.TOTP(secret).verify(codigo, valid_window=1)
