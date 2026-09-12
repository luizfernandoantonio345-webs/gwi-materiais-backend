from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.estoque import TipoMovimento
from ..models.material import Material
from ..models.pedido import HistoricoPedido, ItemPedido, Pedido, StatusPedido
from ..models.usuario import Papel
from ..schemas.api import AprovacaoGerente, EfetivarCompra, Pagina, PedidoCreate, PedidoOut
from ..security.deps import CurrentUser, require_roles
from ..realtime import publicar_evento
from ..services import audit_service
from ..services.estoque_service import movimentar
from ..services.workflow import destino_por_alcada, transicionar

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


async def _numero(db: AsyncSession) -> str:
    total = await db.scalar(select(func.count()).select_from(Pedido))
    return f"REQ-{datetime.now(UTC).year}-{(total or 0) + 1:05d}"


async def _get(db: AsyncSession, pedido_id: int) -> Pedido:
    p = await db.get(Pedido, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return p


@router.post("", response_model=PedidoOut, status_code=201, dependencies=[Depends(require_roles(Papel.ALMOXARIFE, Papel.GERENTE))])
async def criar_pedido(dados: PedidoCreate, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    pedido = Pedido(
        numero=await _numero(db),
        status=StatusPedido.AGUARDANDO_GERENTE,
        urgencia=dados.urgencia,
        justificativa=dados.justificativa,
        solicitante_id=usuario.id,
        criado_por=usuario.id,
    )
    total = Decimal(0)
    for item in dados.itens:
        material = await db.get(Material, item.material_id)
        if not material:
            raise HTTPException(status_code=404, detail=f"Material {item.material_id} inexistente.")
        pedido.itens.append(ItemPedido(material_id=material.id, qtd_solicitada=item.qtd_solicitada, custo_unitario=material.custo_medio))
        total += Decimal(str(item.qtd_solicitada)) * Decimal(str(material.custo_medio))
    pedido.valor_estimado = float(total)
    db.add(pedido)
    await db.flush()
    db.add(
        HistoricoPedido(
            pedido_id=pedido.id,
            de_status=None,
            para_status=StatusPedido.AGUARDANDO_GERENTE.value,
            usuario_id=usuario.id,
            observacao="Pedido criado",
        )
    )
    await audit_service.registrar(db, "pedido_criado", "pedido", usuario.id, str(pedido.id))
    await db.flush()
    await db.refresh(pedido)
    await publicar_evento(["GERENTE"], "pedido_novo", "Novo pedido para aprovação.")
    return pedido


@router.get("", response_model=Pagina[PedidoOut])
async def listar(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filtro: StatusPedido | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Pedido)
    if status_filtro:
        stmt = stmt.where(Pedido.status == status_filtro)
    elif usuario.papel == Papel.GERENTE:
        stmt = stmt.where(Pedido.status == StatusPedido.AGUARDANDO_GERENTE)
    elif usuario.papel == Papel.ADM_COMPRAS:
        stmt = stmt.where(Pedido.status.in_([StatusPedido.AGUARDANDO_COMPRA, StatusPedido.COMPRADO]))
    total = int(await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    stmt = stmt.order_by(Pedido.criado_em.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    return Pagina(items=list(res.scalars().all()), total=total, limit=limit, offset=offset)


@router.get("/{pedido_id}", response_model=PedidoOut)
async def detalhar(pedido_id: int, _: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _get(db, pedido_id)


@router.post("/{pedido_id}/aprovar", response_model=PedidoOut)
async def aprovar(pedido_id: int, dados: AprovacaoGerente, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if usuario.papel != Papel.GERENTE:
        raise HTTPException(status_code=403, detail="Apenas gestão aprova.")
    pedido = await _get(db, pedido_id)
    mapa = {i.id: i for i in pedido.itens}
    for ap in dados.itens:
        item = mapa.get(ap.item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {ap.item_id} não é deste pedido.")
        if ap.qtd_aprovada > float(item.qtd_solicitada):
            raise HTTPException(status_code=422, detail="Aprovado não pode superar solicitado.")
        item.qtd_aprovada = ap.qtd_aprovada
    for item in pedido.itens:
        if item.qtd_aprovada is None:
            item.qtd_aprovada = item.qtd_solicitada

    valor = sum(Decimal(str(i.qtd_aprovada)) * Decimal(str(i.custo_unitario)) for i in pedido.itens)
    pedido.valor_estimado = float(valor)

    if all(float(i.qtd_aprovada) == 0 for i in pedido.itens):
        await transicionar(db, pedido, StatusPedido.REJEITADO, usuario, dados.observacao or "Itens zerados")
        await publicar_evento(["ALMOXARIFE"], "pedido_status", f"Pedido {pedido.numero} foi rejeitado.")
    else:
        destino = destino_por_alcada(float(valor), usuario) if pedido.status == StatusPedido.AGUARDANDO_GERENTE else StatusPedido.APROVADO
        await transicionar(db, pedido, destino, usuario, dados.observacao)
        # Aprovação é autorização de gasto (gestão) — não consome/reserva estoque.
        if destino == StatusPedido.APROVADO:
            await transicionar(db, pedido, StatusPedido.AGUARDANDO_COMPRA, usuario, "Encaminhado à compra")
            await publicar_evento(["ADM_COMPRAS"], "pedido_compra", "Novo pedido aprovado para compra.")
    await audit_service.registrar(db, "pedido_aprovado", "pedido", usuario.id, str(pedido.id), f"valor={valor}")
    await db.flush()
    await db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/comprar", response_model=PedidoOut)
async def comprar(pedido_id: int, dados: EfetivarCompra, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    pedido = await _get(db, pedido_id)
    mapa = {i.id: i for i in pedido.itens}
    for c in dados.itens:
        item = mapa.get(c.item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {c.item_id} inválido.")
        item.qtd_comprada = c.qtd_comprada
        item.custo_unitario = c.custo_unitario
    await transicionar(db, pedido, StatusPedido.COMPRADO, usuario, dados.observacao)
    await audit_service.registrar(db, "pedido_comprado", "pedido", usuario.id, str(pedido.id))
    await db.flush()
    await db.refresh(pedido)
    await publicar_evento(["ALMOXARIFE", "GERENTE"], "pedido_status", f"Pedido {pedido.numero} foi comprado.")
    return pedido


@router.post("/{pedido_id}/receber", response_model=PedidoOut)
async def receber(pedido_id: int, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    pedido = await _get(db, pedido_id)
    for item in pedido.itens:
        if item.qtd_comprada and float(item.qtd_comprada) > 0:
            material = await db.get(Material, item.material_id)
            await movimentar(
                db,
                material,
                TipoMovimento.ENTRADA,
                float(item.qtd_comprada),
                usuario.id,
                float(item.custo_unitario),
                observacao=f"Entrada {pedido.numero}",
            )
    await transicionar(db, pedido, StatusPedido.RECEBIDO, usuario)
    await audit_service.registrar(db, "pedido_recebido", "pedido", usuario.id, str(pedido.id))
    await db.flush()
    await db.refresh(pedido)
    await publicar_evento(["ALMOXARIFE", "GERENTE"], "pedido_status", f"Pedido {pedido.numero} recebido — estoque atualizado.")
    return pedido
