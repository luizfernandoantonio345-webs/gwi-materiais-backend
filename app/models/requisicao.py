import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TenantMixin, agora


class StatusRequisicao(str, enum.Enum):
    PENDENTE  = "PENDENTE"
    COMPRADO  = "COMPRADO"
    RECEBIDO  = "RECEBIDO"
    CANCELADO = "CANCELADO"


class RequisicaoEstoque(Base, TenantMixin):
    __tablename__ = "requisicoes_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"), index=True)
    quantidade: Mapped[float] = mapped_column(Numeric(14, 3))
    observacao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[StatusRequisicao] = mapped_column(
        Enum(StatusRequisicao), default=StatusRequisicao.PENDENTE, index=True
    )
    almoxarife_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    compras_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    recebido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    material     = relationship("Material")
    almoxarife   = relationship("Usuario", foreign_keys=[almoxarife_id])
    comprador    = relationship("Usuario", foreign_keys=[compras_id])
