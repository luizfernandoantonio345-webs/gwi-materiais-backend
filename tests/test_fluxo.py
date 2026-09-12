from tests.conftest import hdr


async def _material(client, h, codigo):
    r = await client.get("/materiais", headers=h)
    return next(m for m in r.json()["items"] if m["codigo"] == codigo)


async def test_fluxo_completo_aprovacao_e_compra(client):
    almox = await hdr(client, "almox@g.com")
    gerente = await hdr(client, "gerente@g.com")
    compras = await hdr(client, "compras@g.com")

    await client.post(
        "/estoque/entrada",
        headers=compras,
        json={"material_id": (await _material(client, compras, "DISCO-115"))["id"], "quantidade": 1000, "custo_unitario": 5.0},
    )

    disco = await _material(client, almox, "DISCO-115")
    r = await client.post(
        "/pedidos", headers=almox, json={"urgencia": "ALTA", "itens": [{"material_id": disco["id"], "qtd_solicitada": 500}]}
    )
    assert r.status_code == 201, r.text
    pedido = r.json()
    assert pedido["status"] == "AGUARDANDO_GERENTE"
    item_id = pedido["itens"][0]["id"]

    r = await client.post(f"/pedidos/{pedido['id']}/aprovar", headers=gerente, json={"itens": [{"item_id": item_id, "qtd_aprovada": 200}]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "AGUARDANDO_COMPRA"

    # Aprovação não reserva estoque (é autorização de gasto, não consumo).
    disco = await _material(client, almox, "DISCO-115")
    assert disco["saldo_reservado"] == 0
    assert disco["saldo_disponivel"] == 1000

    r = await client.post(
        f"/pedidos/{pedido['id']}/comprar",
        headers=compras,
        json={"itens": [{"item_id": item_id, "qtd_comprada": 200, "custo_unitario": 5.1}]},
    )
    assert r.json()["status"] == "COMPRADO"
    r = await client.post(f"/pedidos/{pedido['id']}/receber", headers=compras)
    assert r.json()["status"] == "RECEBIDO"

    disco = await _material(client, almox, "DISCO-115")
    assert disco["saldo_estoque"] == 1200
    assert disco["saldo_reservado"] == 0


async def test_comodato_abre_e_devolve(client):
    almox = await hdr(client, "almox@g.com")
    compras = await hdr(client, "compras@g.com")
    fur = await _material(client, compras, "FUR-BOSCH")
    await client.post("/estoque/entrada", headers=compras, json={"material_id": fur["id"], "quantidade": 5, "custo_unitario": 480})

    r = await client.post("/estoque/baixa-qr", headers=almox, json={"codigo_material": "FUR-BOSCH", "quantidade": 1, "matricula": "00123"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ABERTO"
    cid = r.json()["comodato_id"]

    r = await client.post("/comodatos/devolver", headers=almox, json={"comodato_id": cid})
    assert r.json()["status"] == "DEVOLVIDO"


async def test_kardex_integridade(client):
    compras = await hdr(client, "compras@g.com")
    disco = await _material(client, compras, "DISCO-115")
    for _ in range(3):
        await client.post("/estoque/entrada", headers=compras, json={"material_id": disco["id"], "quantidade": 10, "custo_unitario": 5})
    r = await client.get(f"/estoque/integridade/{disco['id']}", headers=compras)
    assert r.json()["kardex_integro"] is True
