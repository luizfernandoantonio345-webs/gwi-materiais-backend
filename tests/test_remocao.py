import pytest

from .conftest import hdr

pytestmark = pytest.mark.asyncio


async def _id_material(client, h, busca):
    r = await client.get(f"/materiais?busca={busca}", headers=h)
    itens = r.json()["items"]
    return itens[0]["id"] if itens else None


async def _id_colaborador(client, h, busca):
    r = await client.get(f"/colaboradores?busca={busca}", headers=h)
    itens = r.json()["items"]
    return itens[0]["id"] if itens else None


async def test_remover_material_some_da_listagem(client):
    h = await hdr(client, "compras@g.com")
    mid = await _id_material(client, h, "DISCO-115")
    assert mid is not None

    r = await client.delete(f"/materiais/{mid}", headers=h)
    assert r.status_code == 204

    assert await _id_material(client, h, "DISCO-115") is None


async def test_remover_material_inexistente(client):
    h = await hdr(client, "compras@g.com")
    r = await client.delete("/materiais/999999", headers=h)
    assert r.status_code == 404


async def test_remover_material_duas_vezes(client):
    h = await hdr(client, "compras@g.com")
    mid = await _id_material(client, h, "FUR-BOSCH")
    assert (await client.delete(f"/materiais/{mid}", headers=h)).status_code == 204
    assert (await client.delete(f"/materiais/{mid}", headers=h)).status_code == 404


async def test_almoxarife_nao_remove_material(client):
    h = await hdr(client, "almox@g.com")
    r = await client.delete("/materiais/1", headers=h)
    assert r.status_code == 403


async def test_remover_colaborador_some_da_listagem(client):
    h = await hdr(client, "compras@g.com")
    cid = await _id_colaborador(client, h, "00123")
    assert cid is not None

    r = await client.delete(f"/colaboradores/{cid}", headers=h)
    assert r.status_code == 204

    assert await _id_colaborador(client, h, "00123") is None

    # remover de novo (já inativo) → 404
    r = await client.delete(f"/colaboradores/{cid}", headers=h)
    assert r.status_code == 404


async def test_remover_colaborador_inexistente(client):
    h = await hdr(client, "compras@g.com")
    r = await client.delete("/colaboradores/999999", headers=h)
    assert r.status_code == 404
