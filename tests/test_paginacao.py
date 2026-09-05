from tests.conftest import hdr


async def _classe_id(client, h):
    r = await client.get("/classes", headers=h)
    return r.json()["items"][0]["id"]


async def test_materiais_retorna_envelope(client):
    compras = await hdr(client, "compras@g.com")
    r = await client.get("/materiais", headers=compras)
    corpo = r.json()
    assert set(corpo.keys()) == {"items", "total", "limit", "offset"}
    assert isinstance(corpo["items"], list)
    assert corpo["total"] >= len(corpo["items"])


async def test_paginacao_limita_e_desloca(client):
    compras = await hdr(client, "compras@g.com")
    cid = await _classe_id(client, compras)
    for i in range(15):
        await client.post(
            "/materiais",
            headers=compras,
            json={"codigo": f"PAG-{i:03d}", "nome": f"Item paginado {i:03d}", "tipo": "CONSUMIVEL", "classe_id": cid},
        )
    p1 = (await client.get("/materiais?limit=10&offset=0", headers=compras)).json()
    p2 = (await client.get("/materiais?limit=10&offset=10", headers=compras)).json()
    assert len(p1["items"]) == 10
    assert p1["total"] >= 17
    ids1 = {m["id"] for m in p1["items"]}
    ids2 = {m["id"] for m in p2["items"]}
    assert ids1.isdisjoint(ids2)


async def test_busca_por_codigo_e_nome(client):
    compras = await hdr(client, "compras@g.com")
    cid = await _classe_id(client, compras)
    await client.post(
        "/materiais", headers=compras, json={"codigo": "CIMENTO-CP2", "nome": "Cimento CP II 50kg", "tipo": "CONSUMIVEL", "classe_id": cid}
    )
    por_nome = (await client.get("/materiais?busca=cimento", headers=compras)).json()
    assert any(m["codigo"] == "CIMENTO-CP2" for m in por_nome["items"])
    por_codigo = (await client.get("/materiais?busca=CP2", headers=compras)).json()
    assert any(m["codigo"] == "CIMENTO-CP2" for m in por_codigo["items"])


async def test_limite_invalido_rejeitado(client):
    compras = await hdr(client, "compras@g.com")
    r = await client.get("/materiais?limit=999", headers=compras)
    assert r.status_code == 422
