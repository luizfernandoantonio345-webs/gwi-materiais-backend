import pytest

from .conftest import hdr

pytestmark = pytest.mark.asyncio


async def test_editar_proprio_perfil(client):
    h = await hdr(client, "almox@g.com")

    # estado inicial: sem foto
    r = await client.get("/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json()["foto"] is None

    # atualiza nome + foto
    foto = "data:image/jpeg;base64,/9j/AAAQSk"
    r = await client.patch("/auth/me", headers=h, json={"nome": "Ana Ribeiro", "foto": foto})
    assert r.status_code == 200
    body = r.json()
    assert body["nome"] == "Ana Ribeiro"
    assert body["foto"] == foto

    # persistiu
    r = await client.get("/auth/me", headers=h)
    assert r.json()["nome"] == "Ana Ribeiro"
    assert r.json()["foto"] == foto

    # string vazia remove a foto
    r = await client.patch("/auth/me", headers=h, json={"foto": ""})
    assert r.status_code == 200
    assert r.json()["foto"] is None


async def test_nome_vazio_rejeitado(client):
    h = await hdr(client, "almox@g.com")
    r = await client.patch("/auth/me", headers=h, json={"nome": "   "})
    assert r.status_code == 422


async def test_editar_perfil_exige_autenticacao(client):
    r = await client.patch("/auth/me", json={"nome": "Hacker"})
    assert r.status_code == 401
