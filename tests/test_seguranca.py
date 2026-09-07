import pytest

from tests.conftest import SENHA, hdr


# ---------------------------------------------------- autenticação
async def test_sem_token_bloqueia(client):
    r = await client.get("/pedidos")
    assert r.status_code == 401


async def test_token_invalido_bloqueia(client):
    r = await client.get("/pedidos", headers={"Authorization": "Bearer lixo.invalido.token"})
    assert r.status_code == 401


async def test_token_adulterado_bloqueia(client):
    h = await hdr(client, "gerente@g.com")
    adulterado = h["Authorization"][:-4] + "AAAA"
    r = await client.get("/pedidos", headers={"Authorization": adulterado})
    assert r.status_code == 401


# ---------------------------------------------------- autorização (RBAC)
async def test_almoxarife_nao_aprova(client):
    almox = await hdr(client, "almox@g.com")
    disco = next(m for m in (await client.get("/materiais", headers=almox)).json()["items"] if m["codigo"] == "DISCO-115")
    ped = (await client.post("/pedidos", headers=almox, json={"itens": [{"material_id": disco["id"], "qtd_solicitada": 10}]})).json()
    r = await client.post(
        f"/pedidos/{ped['id']}/aprovar", headers=almox, json={"itens": [{"item_id": ped["itens"][0]["id"], "qtd_aprovada": 10}]}
    )
    assert r.status_code == 403


async def test_compras_nao_cadastra_usuario(client):
    compras = await hdr(client, "compras@g.com")
    r = await client.post(
        "/auth/usuarios", headers=compras, json={"nome": "X", "email": "x@g.com", "senha": "Abcdef12345!", "papel": "GERENTE"}
    )
    assert r.status_code == 403


async def test_almoxarife_nao_cadastra_material(client):
    almox = await hdr(client, "almox@g.com")
    r = await client.post("/materiais", headers=almox, json={"codigo": "X", "nome": "X", "tipo": "CONSUMIVEL", "classe_id": 1})
    assert r.status_code == 403


# ---------------------------------------------------- brute force
async def test_lockout_apos_tentativas(client):
    for _ in range(5):
        r = await client.post("/auth/login", data={"username": "gerente@g.com", "password": "errada"})
        assert r.status_code == 401
    r = await client.post("/auth/login", data={"username": "gerente@g.com", "password": SENHA})
    assert r.status_code == 429


# ---------------------------------------------------- injeção
@pytest.mark.parametrize(
    "payload",
    [
        "' OR '1'='1",
        "admin'--",
        "'; DROP TABLE usuarios;--",
        '" OR 1=1--',
    ],
)
async def test_sql_injection_login(client, payload):
    r = await client.post("/auth/login", data={"username": payload, "password": payload})
    assert r.status_code in (401, 429)
    async with __import__("app.database", fromlist=["SessionLocal"]).SessionLocal() as db:
        from sqlalchemy import select

        from app.models.usuario import Usuario

        assert (await db.execute(select(Usuario))).scalars().first() is not None


async def test_injection_em_material(client):
    compras = await hdr(client, "compras@g.com")
    r = await client.get("/materiais", headers=compras, params={"abaixo_minimo": "'; DROP TABLE materiais;--"})
    assert r.status_code in (200, 422)


async def test_erro_nao_vaza_stacktrace(client):
    compras = await hdr(client, "compras@g.com")
    r = await client.post("/estoque/entrada", headers=compras, json={"material_id": 999999, "quantidade": 1, "custo_unitario": 1})
    assert r.status_code == 404
    corpo = r.text.lower()
    assert "traceback" not in corpo and "sqlalchemy" not in corpo and 'file "' not in corpo


# ---------------------------------------------------- headers de segurança
async def test_security_headers(client):
    r = await client.get("/health/live")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in r.headers
    assert "Content-Security-Policy" in r.headers
    assert "Server" not in r.headers


# ---------------------------------------------------- aprovação (nível único: gerente aprova tudo)
async def test_gerente_aprova_alto_valor_direto(client):
    almox = await hdr(client, "almox@g.com")
    gerente = await hdr(client, "gerente@g.com")
    compras = await hdr(client, "compras@g.com")
    fur = next(m for m in (await client.get("/materiais", headers=compras)).json()["items"] if m["codigo"] == "FUR-BOSCH")
    await client.post("/estoque/entrada", headers=compras, json={"material_id": fur["id"], "quantidade": 1000, "custo_unitario": 480})

    ped = (await client.post("/pedidos", headers=almox, json={"itens": [{"material_id": fur["id"], "qtd_solicitada": 500}]})).json()
    r = await client.post(
        f"/pedidos/{ped['id']}/aprovar", headers=gerente, json={"itens": [{"item_id": ped["itens"][0]["id"], "qtd_aprovada": 500}]}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "AGUARDANDO_COMPRA"


# ---------------------------------------------------- idempotência
async def test_idempotencia_nao_duplica(client):
    almox = await hdr(client, "almox@g.com")
    disco = next(m for m in (await client.get("/materiais", headers=almox)).json()["items"] if m["codigo"] == "DISCO-115")
    corpo = {"itens": [{"material_id": disco["id"], "qtd_solicitada": 10}]}
    chave = {"Idempotency-Key": "abc-123", **almox}
    r1 = await client.post("/pedidos", headers=chave, json=corpo)
    r2 = await client.post("/pedidos", headers=chave, json=corpo)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["numero"] == r2.json()["numero"]
    total = len((await client.get("/pedidos", headers=almox)).json()["items"])
    assert total == 1


# ---------------------------------------------------- reserva de saldo
async def test_reserva_impede_estouro_saldo(client):
    almox = await hdr(client, "almox@g.com")
    gerente = await hdr(client, "gerente@g.com")
    compras = await hdr(client, "compras@g.com")
    disco = next(m for m in (await client.get("/materiais", headers=compras)).json()["items"] if m["codigo"] == "DISCO-115")
    await client.post("/estoque/entrada", headers=compras, json={"material_id": disco["id"], "quantidade": 100, "custo_unitario": 5})

    p1 = (await client.post("/pedidos", headers=almox, json={"itens": [{"material_id": disco["id"], "qtd_solicitada": 80}]})).json()
    p2 = (await client.post("/pedidos", headers=almox, json={"itens": [{"material_id": disco["id"], "qtd_solicitada": 80}]})).json()

    r1 = await client.post(
        f"/pedidos/{p1['id']}/aprovar", headers=gerente, json={"itens": [{"item_id": p1["itens"][0]["id"], "qtd_aprovada": 80}]}
    )
    assert r1.json()["status"] == "AGUARDANDO_COMPRA"
    r2 = await client.post(
        f"/pedidos/{p2['id']}/aprovar", headers=gerente, json={"itens": [{"item_id": p2["itens"][0]["id"], "qtd_aprovada": 80}]}
    )
    assert r2.status_code == 409


# ---------------------------------------------------- MFA
async def test_mfa_fluxo(client):
    import pyotp

    gerente = await hdr(client, "gerente@g.com")
    setup = (await client.post("/auth/mfa/setup", headers=gerente)).json()
    secret = setup["secret"]
    codigo = pyotp.TOTP(secret).now()
    r = await client.post("/auth/mfa/ativar", headers=gerente, json={"desafio_id": "x", "codigo": codigo})
    assert r.status_code == 204

    r = await client.post("/auth/login", data={"username": "gerente@g.com", "password": SENHA})
    assert r.json()["mfa_requerido"] is True
    desafio = r.json()["desafio_id"]

    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": "000000"})
    assert r.status_code == 401

    r = await client.post("/auth/mfa/verify", json={"desafio_id": desafio, "codigo": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and r.json()["access_token"]


# ---------------------------------------------------- refresh / rotação
async def test_refresh_rotaciona_e_revoga(client):
    r = await client.post("/auth/login", data={"username": "gerente@g.com", "password": SENHA})
    refresh = r.json()["refresh_token"]
    r1 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    r2 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


# ---------------------------------------------------- senha fraca
async def test_senha_fraca_rejeitada(client):
    gerente = await hdr(client, "gerente@g.com")
    r = await client.post(
        "/auth/usuarios", headers=gerente, json={"nome": "Fraco", "email": "fraco@g.com", "senha": "123456", "papel": "ALMOXARIFE"}
    )
    assert r.status_code == 422


# ---------------------------------------------------- gestão de usuários
async def test_gerente_gerencia_usuarios(client):
    gerente = await hdr(client, "gerente@g.com")

    lista = (await client.get("/auth/usuarios", headers=gerente)).json()
    assert lista["total"] >= 3

    r = await client.post(
        "/auth/usuarios",
        headers=gerente,
        json={"nome": "Novo Almox", "email": "novo@g.com", "senha": SENHA, "papel": "ALMOXARIFE"},
    )
    assert r.status_code == 201, r.text
    novo_id = r.json()["id"]

    r = await client.patch(f"/auth/usuarios/{novo_id}", headers=gerente, json={"nome": "Renomeado", "ativo": False})
    assert r.status_code == 200
    assert r.json()["nome"] == "Renomeado" and r.json()["ativo"] is False


async def test_papel_diretor_rejeitado(client):
    gerente = await hdr(client, "gerente@g.com")
    r = await client.post(
        "/auth/usuarios",
        headers=gerente,
        json={"nome": "X", "email": "diretor2@g.com", "senha": SENHA, "papel": "DIRETOR"},
    )
    assert r.status_code == 422


async def test_almoxarife_nao_lista_usuarios(client):
    almox = await hdr(client, "almox@g.com")
    r = await client.get("/auth/usuarios", headers=almox)
    assert r.status_code == 403
