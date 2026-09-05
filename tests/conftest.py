import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_gwi.db")
os.environ["RATE_LIMIT_PER_MIN"] = "100000"
os.environ["RATE_LIMIT_LOGIN_PER_MIN"] = "100000"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-suite-only-not-production"

import httpx
import pytest_asyncio
from httpx import ASGITransport

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.catalogo import ClasseMaterial, Colaborador, Material, TipoMaterial
from app.models.usuario import Papel, Usuario
from app.security.passwords import hash_senha

SENHA = "Gramo@Forte2026!"
BASE = "http://test"


async def _seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        db.add_all(
            [
                Usuario(nome="Ana", email="almox@g.com", senha_hash=hash_senha(SENHA), papel=Papel.ALMOXARIFE, limite_alcada=0),
                Usuario(nome="Carlos", email="compras@g.com", senha_hash=hash_senha(SENHA), papel=Papel.ADM_COMPRAS, limite_alcada=0),
                Usuario(nome="Rita", email="gerente@g.com", senha_hash=hash_senha(SENHA), papel=Papel.GERENTE, limite_alcada=50000),
                Usuario(nome="Paulo", email="diretor@g.com", senha_hash=hash_senha(SENHA), papel=Papel.DIRETOR, limite_alcada=10_000_000),
            ]
        )
        c1 = ClasseMaterial(codigo="ABR", nome="Abrasivos")
        c2 = ClasseMaterial(codigo="FER", nome="Ferramentas")
        db.add_all([c1, c2])
        await db.flush()
        db.add_all(
            [
                Material(
                    codigo="DISCO-115",
                    nome="Disco corte 115",
                    tipo=TipoMaterial.CONSUMIVEL,
                    unidade="UN",
                    classe_id=c1.id,
                    estoque_minimo=50,
                    custo_medio=5.0,
                    saldo_estoque=0,
                ),
                Material(
                    codigo="FUR-BOSCH",
                    nome="Furadeira Bosch",
                    tipo=TipoMaterial.FERRAMENTA,
                    unidade="UN",
                    classe_id=c2.id,
                    estoque_minimo=2,
                    custo_medio=480.0,
                    saldo_estoque=0,
                ),
            ]
        )
        db.add(Colaborador(matricula="00123", nome="Joao", cargo="Serralheiro", centro_custo="OBRA-01"))
        await db.commit()


@pytest_asyncio.fixture
async def client():
    await _seed()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


async def login(client, email, senha=SENHA):
    r = await client.post("/auth/login", data={"username": email, "password": senha})
    if r.status_code != 200:
        return None, r
    data = r.json()
    if data.get("mfa_requerido"):
        return None, r
    return {"Authorization": f"Bearer {data['access_token']}"}, r


async def hdr(client, email):
    h, _ = await login(client, email)
    return h
