import pyotp
import pytest

from .conftest import SENHA, hdr, login

pytestmark = pytest.mark.asyncio


async def _ativar_mfa(client, h):
    r = await client.post("/auth/mfa/setup", headers=h)
    assert r.status_code == 200
    secret = r.json()["secret"]
    codigo = pyotp.TOTP(secret).now()
    r = await client.post("/auth/mfa/ativar", headers=h, json={"desafio_id": "x", "codigo": codigo})
    assert r.status_code == 200
    return secret, r.json()["backup_codes"]


async def test_login_sem_mfa_entra_direto(client):
    h, r = await login(client, "compras@g.com")
    assert h is not None
    assert r.json()["mfa_requerido"] is False


async def test_ativar_gera_backup_codes(client):
    h = await hdr(client, "almox@g.com")
    _, backup = await _ativar_mfa(client, h)
    assert isinstance(backup, list) and len(backup) == 8


async def test_login_com_mfa_exige_codigo(client):
    h = await hdr(client, "almox@g.com")
    secret, _ = await _ativar_mfa(client, h)

    r = await client.post("/auth/login", data={"username": "almox@g.com", "password": SENHA})
    body = r.json()
    assert body["mfa_requerido"] is True
    desafio = body["desafio_id"]

    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_codigo_invalido_rejeitado(client):
    h = await hdr(client, "almox@g.com")
    await _ativar_mfa(client, h)
    r = await client.post("/auth/login", data={"username": "almox@g.com", "password": SENHA})
    desafio = r.json()["desafio_id"]
    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": "000000"})
    assert r.status_code == 401


async def test_backup_code_funciona_e_nao_reutiliza(client):
    h = await hdr(client, "almox@g.com")
    _, backup = await _ativar_mfa(client, h)
    code = backup[0]

    r = await client.post("/auth/login", data={"username": "almox@g.com", "password": SENHA})
    desafio = r.json()["desafio_id"]
    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": code})
    assert r.status_code == 200

    r = await client.post("/auth/login", data={"username": "almox@g.com", "password": SENHA})
    desafio = r.json()["desafio_id"]
    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": code})
    assert r.status_code == 401


async def test_desativar_com_senha(client):
    h = await hdr(client, "almox@g.com")
    await _ativar_mfa(client, h)

    r = await client.post("/auth/mfa/desativar", headers=h, json={"senha": "errada"})
    assert r.status_code == 401

    r = await client.post("/auth/mfa/desativar", headers=h, json={"senha": SENHA})
    assert r.status_code == 204

    r = await client.post("/auth/login", data={"username": "almox@g.com", "password": SENHA})
    assert r.json()["mfa_requerido"] is False
