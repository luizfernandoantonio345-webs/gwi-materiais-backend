import pyotp


def gerar_secret() -> str:
    return pyotp.random_base32()


def uri_provisionamento(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="GWI Materiais")


def verificar_codigo(secret: str, codigo: str) -> bool:
    if not secret or not codigo:
        return False
    return pyotp.TOTP(secret).verify(codigo, valid_window=1)
