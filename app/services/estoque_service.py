import hashlib
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.estoque import MovimentacaoEstoque, TipoMovimento
from ..models.material import Material


async def _ultimo_hash(db: AsyncSession, material_id: int) -> str:
    res = await db.execute(
        select(MovimentacaoEstoque.hash_atual)
        .where(MovimentacaoEstoque.material_id == material_id)
        .order_by(MovimentacaoEstoque.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none() or ""


def _calcular_hash(anterior: str, material_id: int, tipo: str, qtd: float, saldo: float, usuario_id: int) -> str:
    base = f"{anterior}|{material_id}|{tipo}|{qtd}|{saldo}|{usuario_id}"
    return hashlib.sha256(base.encode()).hexdigest()


async def movimentar(
    db: AsyncSession,
    material: Material,
    tipo: TipoMovimento,
    quantidade: float,
    usuario_id: int,
    custo_unitario: float = 0.0,
    colaborador_id: int | None = None,
    observacao: str | None = None,
) -> MovimentacaoEstoque:
    quantidade = float(quantidade)
    if quantidade <= 0:
        raise HTTPException(status_code=422, detail="Quantidade deve ser positiva.")

    saldo = Decimal(str(material.saldo_estoque))
    qtd = Decimal(str(quantidade))

    if tipo in (TipoMovimento.ENTRADA, TipoMovimento.DEVOLUCAO):
        if tipo == TipoMovimento.ENTRADA and custo_unitario > 0:
            atual = Decimal(str(material.custo_medio))
            novo_saldo = saldo + qtd
            material.custo_medio = float(((saldo * atual + qtd * Decimal(str(custo_unitario))) / novo_saldo) if novo_saldo else Decimal(0))
        material.saldo_estoque = float(saldo + qtd)
    elif tipo == TipoMovimento.SAIDA:
        disponivel = saldo - Decimal(str(material.saldo_reservado))
        if qtd > disponivel:
            raise HTTPException(status_code=409, detail=f"Saldo disponível insuficiente de '{material.nome}': {float(disponivel)}.")
        material.saldo_estoque = float(saldo - qtd)
    elif tipo == TipoMovimento.AJUSTE:
        material.saldo_estoque = quantidade

    material.version += 1
    anterior = await _ultimo_hash(db, material.id)
    h = _calcular_hash(anterior, material.id, tipo.value, quantidade, material.saldo_estoque, usuario_id)
    mov = MovimentacaoEstoque(
        tenant=material.tenant,
        material_id=material.id,
        tipo=tipo,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        saldo_apos=material.saldo_estoque,
        colaborador_id=colaborador_id,
        usuario_id=usuario_id,
        observacao=observacao,
        hash_anterior=anterior,
        hash_atual=h,
    )
    db.add(mov)
    db.add(material)
    return mov


async def verificar_integridade_kardex(db: AsyncSession, material_id: int) -> bool:
    res = await db.execute(
        select(MovimentacaoEstoque).where(MovimentacaoEstoque.material_id == material_id).order_by(MovimentacaoEstoque.id.asc())
    )
    anterior = ""
    for mov in res.scalars().all():
        esperado = _calcular_hash(anterior, mov.material_id, mov.tipo.value, float(mov.quantidade), float(mov.saldo_apos), mov.usuario_id)
        if mov.hash_anterior != anterior or mov.hash_atual != esperado:
            return False
        anterior = mov.hash_atual
    return True
