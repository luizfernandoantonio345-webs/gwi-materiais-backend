from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.colaborador import Colaborador
from ..models.material import ClasseMaterial, Material
from ..models.usuario import Papel
from ..schemas.api import (
    ClasseCreate,
    ClasseOut,
    ColaboradorCreate,
    ColaboradorOut,
    MaterialCreate,
    MaterialOut,
    Pagina,
)
from ..security.deps import CurrentUser, require_roles

router = APIRouter(tags=["Catálogo"])
somente_adm = require_roles(Papel.ADM_COMPRAS)

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


async def _contar(db: AsyncSession, stmt) -> int:
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    return int(total or 0)


@router.post("/classes", response_model=ClasseOut, status_code=201, dependencies=[Depends(somente_adm)])
async def criar_classe(dados: ClasseCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    classe = ClasseMaterial(**dados.model_dump())
    db.add(classe)
    await db.flush()
    await db.refresh(classe)
    return classe


@router.get("/classes", response_model=Pagina[ClasseOut])
async def listar_classes(_: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)], limit: Limit = 50, offset: Offset = 0):
    base = select(ClasseMaterial).order_by(ClasseMaterial.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    return Pagina(items=list(res.scalars().all()), total=total, limit=limit, offset=offset)


@router.post("/materiais", response_model=MaterialOut, status_code=201, dependencies=[Depends(somente_adm)])
async def criar_material(dados: MaterialCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    if not await db.get(ClasseMaterial, dados.classe_id):
        raise HTTPException(status_code=404, detail="Classe não encontrada.")
    existe = await db.execute(select(Material).where(Material.codigo == dados.codigo))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Código já existe.")
    material = Material(**dados.model_dump())
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return material


@router.get("/materiais", response_model=Pagina[MaterialOut])
async def listar_materiais(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    abaixo_minimo: bool = False,
    busca: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    base = select(Material).where(Material.ativo.is_(True))
    if busca:
        termo = f"%{busca.strip()}%"
        base = base.where(or_(Material.nome.ilike(termo), Material.codigo.ilike(termo)))
    base = base.order_by(Material.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    itens = list(res.scalars().all())
    if abaixo_minimo:
        itens = [m for m in itens if m.abaixo_do_minimo]
    return Pagina(items=itens, total=total, limit=limit, offset=offset)


@router.post(
    "/colaboradores",
    response_model=ColaboradorOut,
    status_code=201,
    dependencies=[Depends(require_roles(Papel.ADM_COMPRAS, Papel.ALMOXARIFE))],
)
async def criar_colaborador(dados: ColaboradorCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existe = await db.execute(select(Colaborador).where(Colaborador.matricula == dados.matricula))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Matrícula já cadastrada.")
    colab = Colaborador(**dados.model_dump())
    db.add(colab)
    await db.flush()
    await db.refresh(colab)
    return colab


@router.get("/colaboradores", response_model=Pagina[ColaboradorOut])
async def listar_colaboradores(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    busca: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    base = select(Colaborador)
    if busca:
        termo = f"%{busca.strip()}%"
        base = base.where(or_(Colaborador.nome.ilike(termo), Colaborador.matricula.ilike(termo)))
    base = base.order_by(Colaborador.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    return Pagina(items=list(res.scalars().all()), total=total, limit=limit, offset=offset)
