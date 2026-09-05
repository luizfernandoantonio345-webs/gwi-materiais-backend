from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pedido import HistoricoPedido, Pedido, StatusPedido
from ..models.usuario import Papel, Usuario

TRANSICOES: dict[StatusPedido, dict[StatusPedido, tuple[Papel, ...]]] = {
    StatusPedido.RASCUNHO: {
        StatusPedido.AGUARDANDO_GERENTE: (Papel.ALMOXARIFE,),
        StatusPedido.CANCELADO: (Papel.ALMOXARIFE,),
    },
    StatusPedido.AGUARDANDO_GERENTE: {
        StatusPedido.APROVADO: (Papel.GERENTE,),
        StatusPedido.AGUARDANDO_DIRETORIA: (Papel.GERENTE,),
        StatusPedido.REJEITADO: (Papel.GERENTE,),
    },
    StatusPedido.AGUARDANDO_DIRETORIA: {
        StatusPedido.APROVADO: (Papel.DIRETOR,),
        StatusPedido.REJEITADO: (Papel.DIRETOR,),
    },
    StatusPedido.APROVADO: {
        StatusPedido.AGUARDANDO_COMPRA: (Papel.GERENTE, Papel.DIRETOR),
    },
    StatusPedido.AGUARDANDO_COMPRA: {
        StatusPedido.COMPRADO: (Papel.ADM_COMPRAS,),
        StatusPedido.REJEITADO: (Papel.ADM_COMPRAS,),
    },
    StatusPedido.COMPRADO: {
        StatusPedido.RECEBIDO: (Papel.ADM_COMPRAS,),
    },
}


def destino_por_alcada(valor: float, aprovador: Usuario) -> StatusPedido:
    if float(aprovador.limite_alcada) >= float(valor):
        return StatusPedido.APROVADO
    return StatusPedido.AGUARDANDO_DIRETORIA


async def transicionar(db: AsyncSession, pedido: Pedido, novo: StatusPedido, usuario: Usuario, observacao: str | None = None) -> Pedido:
    permitido = TRANSICOES.get(pedido.status, {})
    papeis = permitido.get(novo)
    if papeis is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Transição inválida: {pedido.status.value} para {novo.value}.")
    if usuario.papel not in papeis:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem permissão para esta transição.")

    de = pedido.status
    pedido.status = novo
    pedido.version += 1
    if novo in (StatusPedido.APROVADO, StatusPedido.AGUARDANDO_DIRETORIA):
        pedido.aprovador_id = usuario.id
    elif novo in (StatusPedido.COMPRADO, StatusPedido.RECEBIDO):
        pedido.comprador_id = usuario.id

    db.add(HistoricoPedido(pedido_id=pedido.id, de_status=de.value, para_status=novo.value, usuario_id=usuario.id, observacao=observacao))
    return pedido
