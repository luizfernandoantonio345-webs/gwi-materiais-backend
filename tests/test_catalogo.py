import pytest

from .conftest import hdr

pytestmark = pytest.mark.asyncio


async def test_criar_classe_e_listar(client):
    h = await hdr(client, "compras@g.com")
    r = await client.post("/classes", headers=h, json={"codigo": "ELE", "nome": "Elétrico"})
    assert r.status_code == 201
    r = await client.get("/classes", headers=h)
    assert r.status_code == 200 and r.json()["total"] >= 1


async def test_criar_material_regras(client):
    h = await hdr(client, "compras@g.com")
    cid = (await client.get("/classes", headers=h)).json()["items"][0]["id"]

    r = await client.post("/materiais", headers=h, json={
        "codigo": "NEW-001", "nome": "Item novo", "tipo": "CONSUMIVEL",
        "unidade": "UN", "classe_id": cid, "estoque_minimo": 5, "custo_medio": 10,
    })
    assert r.status_code == 201

    r = await client.post("/materiais", headers=h, json={
        "codigo": "NEW-001", "nome": "Duplicado", "tipo": "CONSUMIVEL", "unidade": "UN", "classe_id": cid,
    })
    assert r.status_code == 409

    r = await client.post("/materiais", headers=h, json={
        "codigo": "NEW-002", "nome": "Sem classe", "tipo": "CONSUMIVEL", "unidade": "UN", "classe_id": 999999,
    })
    assert r.status_code == 404


async def test_criar_colaborador_regras(client):
    h = await hdr(client, "compras@g.com")
    r = await client.post("/colaboradores", headers=h, json={"matricula": "55501", "nome": "Novo Colab", "cargo": "Auxiliar"})
    assert r.status_code == 201

    r = await client.post("/colaboradores", headers=h, json={"matricula": "55501", "nome": "Duplicado"})
    assert r.status_code == 409


async def test_listar_materiais_busca_e_abaixo_minimo(client):
    h = await hdr(client, "compras@g.com")
    r = await client.get("/materiais?busca=DISCO", headers=h)
    assert r.status_code == 200
    r = await client.get("/materiais?abaixo_minimo=true", headers=h)
    assert r.status_code == 200
