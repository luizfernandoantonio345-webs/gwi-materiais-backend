from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.colaborador import Colaborador
from ..models.comodato import Comodato, StatusComodato
from ..models.estoque import TipoMovimento
from ..models.material import Material, TipoMaterial
from ..models.usuario import Papel
from ..schemas.api import BaixaQR, DevolucaoQR, EntradaEstoque
from ..security.deps import CurrentUser, require_roles
from ..services import audit_service
from ..services.estoque_service import movimentar, verificar_integridade_kardex

router = APIRouter(tags=["Operações"])


@router.post("/estoque/baixa-qr", dependencies=[Depends(require_roles(Papel.ALMOXARIFE))])
async def baixa_qr(dados: BaixaQR, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(Material).where(Material.codigo == dados.codigo_material))
    material = res.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="QR não corresponde a material.")
    colaborador = None
    if dados.matricula:
        r = await db.execute(select(Colaborador).where(Colaborador.matricula == dados.matricula))
        colaborador = r.scalar_one_or_none()
        if not colaborador:
            raise HTTPException(status_code=404, detail="Matrícula não encontrada.")
    await movimentar(
        db,
        material,
        TipoMovimento.SAIDA,
        dados.quantidade,
        usuario.id,
        colaborador_id=colaborador.id if colaborador else None,
        observacao=dados.observacao,
    )
    if material.tipo == TipoMaterial.FERRAMENTA and colaborador:
        comodato = Comodato(material_id=material.id, colaborador_id=colaborador.id, quantidade=dados.quantidade, almoxarife_id=usuario.id)
        db.add(comodato)
        await db.flush()
        await db.refresh(comodato)
        await audit_service.registrar(db, "comodato_aberto", "comodato", usuario.id, str(comodato.id))
        return {"comodato_id": comodato.id, "status": "ABERTO", "material": material.nome, "colaborador": colaborador.nome}
    await audit_service.registrar(db, "baixa_estoque", "material", usuario.id, str(material.id))
    return {"detail": "Baixa registrada.", "material": material.nome, "saldo_atual": float(material.saldo_estoque)}


@router.post("/comodatos/devolver", dependencies=[Depends(require_roles(Papel.ALMOXARIFE))])
async def devolver(dados: DevolucaoQR, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    comodato = await db.get(Comodato, dados.comodato_id)
    if not comodato:
        raise HTTPException(status_code=404, detail="Comodato não encontrado.")
    if comodato.status != StatusComodato.ABERTO:
        raise HTTPException(status_code=409, detail="Comodato já encerrado.")
    material = await db.get(Material, comodato.material_id)
    await movimentar(
        db,
        material,
        TipoMovimento.DEVOLUCAO,
        float(comodato.quantidade),
        usuario.id,
        colaborador_id=comodato.colaborador_id,
        observacao=dados.observacao or "Devolução",
    )
    comodato.status = StatusComodato.DEVOLVIDO
    comodato.devolvido_em = datetime.now(UTC)
    db.add(comodato)
    await audit_service.registrar(db, "comodato_devolvido", "comodato", usuario.id, str(comodato.id))
    return {"comodato_id": comodato.id, "status": "DEVOLVIDO"}


@router.get("/colaboradores/buscar")
async def buscar_colaboradores(q: str, _: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy import or_
    stmt = select(Colaborador).where(
        Colaborador.ativo == True,
        or_(
            Colaborador.nome.ilike(f"%{q}%"),
            Colaborador.matricula.ilike(f"%{q}%"),
        )
    ).limit(10)
    res = await db.execute(stmt)
    return [{"id": c.id, "matricula": c.matricula, "nome": c.nome, "cargo": c.cargo} for c in res.scalars()]


@router.get("/comodatos/por-colaborador")
async def comodatos_por_colaborador(_: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(Comodato).where(Comodato.status == StatusComodato.ABERTO).order_by(Comodato.retirado_em.desc())
    res = await db.execute(stmt)
    comodatos = res.scalars().all()
    grupos: dict[int, dict] = {}
    for c in comodatos:
        col = await db.get(Colaborador, c.colaborador_id)
        mat = await db.get(Material, c.material_id)
        if c.colaborador_id not in grupos:
            grupos[c.colaborador_id] = {
                "colaborador_id": c.colaborador_id,
                "colaborador_nome": col.nome if col else "—",
                "colaborador_matricula": col.matricula if col else "—",
                "cargo": col.cargo if col else "",
                "itens": [],
            }
        grupos[c.colaborador_id]["itens"].append({
            "comodato_id": c.id,
            "material_id": c.material_id,
            "material_nome": mat.nome if mat else "—",
            "material_codigo": mat.codigo if mat else "—",
            "quantidade": float(c.quantidade),
            "retirado_em": c.retirado_em.isoformat(),
        })
    return list(grupos.values())


@router.get("/estoque/movimentacoes")
async def listar_movimentacoes(
    _: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)],
    material_id: int | None = None,
    colaborador_id: int | None = None,
    almoxarife_id: int | None = None,
    limit: int = 50,
):
    from ..models.estoque import MovimentacaoEstoque
    stmt = select(MovimentacaoEstoque).order_by(MovimentacaoEstoque.criado_em.desc()).limit(limit)
    if material_id:
        stmt = stmt.where(MovimentacaoEstoque.material_id == material_id)
    if colaborador_id:
        stmt = stmt.where(MovimentacaoEstoque.colaborador_id == colaborador_id)
    if almoxarife_id:
        stmt = stmt.where(MovimentacaoEstoque.usuario_id == almoxarife_id)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    out = []
    for m in rows:
        mat = await db.get(Material, m.material_id)
        col = await db.get(Colaborador, m.colaborador_id) if m.colaborador_id else None
        out.append({
            "id": m.id,
            "tipo": m.tipo,
            "material_nome": mat.nome if mat else "—",
            "material_codigo": mat.codigo if mat else "—",
            "colaborador_nome": col.nome if col else None,
            "quantidade": float(m.quantidade),
            "saldo_apos": float(m.saldo_apos),
            "almoxarife_id": m.usuario_id,
            "observacao": m.observacao,
            "criado_em": m.criado_em.isoformat(),
        })
    return out


@router.get("/comodatos")
async def listar_comodatos(_: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)], apenas_abertos: bool = True):
    stmt = select(Comodato).order_by(Comodato.retirado_em.desc())
    if apenas_abertos:
        stmt = stmt.where(Comodato.status == StatusComodato.ABERTO)
    res = await db.execute(stmt)
    return [
        {
            "id": c.id,
            "material_id": c.material_id,
            "colaborador_id": c.colaborador_id,
            "quantidade": float(c.quantidade),
            "status": c.status.value,
        }
        for c in res.scalars().all()
    ]


@router.post("/estoque/entrada", dependencies=[Depends(require_roles(Papel.ADM_COMPRAS))])
async def entrada(dados: EntradaEstoque, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    material = await db.get(Material, dados.material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado.")
    await movimentar(db, material, TipoMovimento.ENTRADA, dados.quantidade, usuario.id, dados.custo_unitario, observacao=dados.observacao)
    return {"material": material.nome, "saldo_atual": float(material.saldo_estoque), "custo_medio": float(material.custo_medio)}


@router.get("/estoque/integridade/{material_id}", dependencies=[Depends(require_roles(Papel.GERENTE, Papel.ADM_COMPRAS))])
async def integridade(material_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    ok = await verificar_integridade_kardex(db, material_id)
    return {"material_id": material_id, "kardex_integro": ok}
