import asyncio

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models.colaborador import Colaborador
from .models.material import ClasseMaterial, Material, TipoMaterial
from .models.usuario import Papel, Usuario
from .security.passwords import hash_senha

SENHA = "Gramo@Forte2026!"

USUARIOS = [
    ("Ana Ribeiro", "almoxarife@gramo.com", Papel.ALMOXARIFE, 0),
    ("Carlos Menezes", "compras@gramo.com", Papel.ADM_COMPRAS, 0),
    ("Rita Duarte", "gerente@gramo.com", Papel.GERENTE, 999_999_999),
]
CLASSES = [("ABR", "Abrasivos"), ("FER", "Ferramentas"), ("EPI", "EPI"), ("ELE", "Elétrica")]
MATERIAIS = [
    ("DISCO-115", "Disco de corte 115mm", TipoMaterial.CONSUMIVEL, "UN", "ABR", 50, 4.9),
    ("FUR-BOSCH", "Furadeira de impacto Bosch", TipoMaterial.FERRAMENTA, "UN", "FER", 2, 480.0),
    ("LUVA-VAQ", "Luva de vaqueta", TipoMaterial.EPI, "PC", "EPI", 100, 12.5),
    ("CABO-2.5", "Cabo flexível 2,5mm2 (m)", TipoMaterial.CONSUMIVEL, "M", "ELE", 200, 2.3),
]
COLABS = [("00123", "João da Silva", "Serralheiro", "OBRA-01"), ("00457", "Maria Souza", "Eletricista", "OBRA-01")]


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        if (await db.execute(select(Usuario).limit(1))).scalar_one_or_none():
            print("Ja populado.")
            return
        for nome, email, papel, alcada in USUARIOS:
            db.add(Usuario(nome=nome, email=email, senha_hash=hash_senha(SENHA), papel=papel, limite_alcada=alcada))
        classes = {}
        for cod, nome in CLASSES:
            c = ClasseMaterial(codigo=cod, nome=nome)
            classes[cod] = c
            db.add(c)
        await db.flush()
        for cod, nome, tipo, un, ccod, mini, custo in MATERIAIS:
            db.add(
                Material(
                    codigo=cod,
                    nome=nome,
                    tipo=tipo,
                    unidade=un,
                    classe_id=classes[ccod].id,
                    estoque_minimo=mini,
                    custo_medio=custo,
                    saldo_estoque=0,
                )
            )
        for mat, nome, cargo, cc in COLABS:
            db.add(Colaborador(matricula=mat, nome=nome, cargo=cargo, centro_custo=cc))
        await db.commit()
        print("Seed concluido. Senha:", SENHA)


if __name__ == "__main__":
    asyncio.run(run())
