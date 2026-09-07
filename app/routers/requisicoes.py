from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.catalogo import Material
from ..models.requisicao import RequisicaoEstoque, StatusRequisicao
from ..models.usuario import Papel
from ..security.deps import CurrentUser, require_roles
from ..services.estoque_service import movimentar
from ..models.estoque import TipoMovimento

router = APIRouter(prefix="/requisicoes", tags=["Requisições"])


class CriarRequisicao(BaseModel):
    material_id: int
    quantidade: float
    observacao: str | None = None


class AtualizarStatus(BaseModel):
    observacao: str | None = None


@router.post("", dependencies=[Depends(require_roles(Papel.ALMOXARIFE))], status_code=201)
async def criar(dados: CriarRequisicao, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    material = await db.get(Material, dados.material_id)
    if not material:
        raise HTTPException(404, "Material não encontrado.")
    # evita duplicata pendente para o mesmo material
    dup = await db.execute(
        select(RequisicaoEstoque).where(
            RequisicaoEstoque.material_id == dados.material_id,
            RequisicaoEstoque.status == StatusRequisicao.PENDENTE,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(409, "Já existe uma requisição pendente para este material.")
    req = RequisicaoEstoque(
        material_id=dados.material_id,
        quantidade=dados.quantidade,
        observacao=dados.observacao,
        almoxarife_id=usuario.id,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {"id": req.id, "status": req.status, "material": material.nome}


@router.get("")
async def listar(_: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)], status: str | None = None):
    stmt = select(RequisicaoEstoque).order_by(RequisicaoEstoque.criado_em.desc())
    if status:
        stmt = stmt.where(RequisicaoEstoque.status == status)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    out = []
    for r in rows:
        mat = await db.get(Material, r.material_id)
        out.append({
            "id": r.id,
            "material_id": r.material_id,
            "material_nome": mat.nome if mat else "—",
            "material_codigo": mat.codigo if mat else "—",
            "quantidade": float(r.quantidade),
            "observacao": r.observacao,
            "status": r.status,
            "almoxarife_id": r.almoxarife_id,
            "criado_em": r.criado_em.isoformat(),
            "recebido_em": r.recebido_em.isoformat() if r.recebido_em else None,
        })
    return out


@router.patch("/{req_id}/comprado", dependencies=[Depends(require_roles(Papel.ADM_COMPRAS))])
async def marcar_comprado(req_id: int, dados: AtualizarStatus, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    req = await db.get(RequisicaoEstoque, req_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada.")
    if req.status != StatusRequisicao.PENDENTE:
        raise HTTPException(409, f"Status atual: {req.status}. Esperado: PENDENTE.")
    req.status = StatusRequisicao.COMPRADO
    req.compras_id = usuario.id
    if dados.observacao:
        req.observacao = (req.observacao or "") + f" | Compras: {dados.observacao}"
    db.add(req)
    await db.commit()
    return {"id": req_id, "status": req.status}


@router.patch("/{req_id}/recebido", dependencies=[Depends(require_roles(Papel.ADM_COMPRAS))])
async def marcar_recebido(req_id: int, dados: AtualizarStatus, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    req = await db.get(RequisicaoEstoque, req_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada.")
    if req.status != StatusRequisicao.COMPRADO:
        raise HTTPException(409, f"Status atual: {req.status}. Esperado: COMPRADO.")
    material = await db.get(Material, req.material_id)
    if not material:
        raise HTTPException(404, "Material não encontrado.")
    await movimentar(db, material, TipoMovimento.ENTRADA, float(req.quantidade), usuario.id,
                     observacao=f"Entrada via requisição #{req_id}")
    req.status = StatusRequisicao.RECEBIDO
    req.recebido_em = datetime.now(UTC)
    req.compras_id = usuario.id
    db.add(req)
    await db.commit()
    return {"id": req_id, "status": req.status, "saldo_atual": float(material.saldo_estoque)}


@router.patch("/{req_id}/cancelar", dependencies=[Depends(require_roles(Papel.ALMOXARIFE))])
async def cancelar(req_id: int, _: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    req = await db.get(RequisicaoEstoque, req_id)
    if not req:
        raise HTTPException(404, "Requisição não encontrada.")
    if req.status not in (StatusRequisicao.PENDENTE,):
        raise HTTPException(409, "Só é possível cancelar requisições PENDENTES.")
    req.status = StatusRequisicao.CANCELADO
    db.add(req)
    await db.commit()
    return {"id": req_id, "status": req.status}
