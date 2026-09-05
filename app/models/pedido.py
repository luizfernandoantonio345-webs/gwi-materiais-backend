import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import AuditMixin, TenantMixin, VersionMixin, agora


class GrauUrgencia(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class StatusPedido(str, enum.Enum):
    RASCUNHO = "RASCUNHO"
    AGUARDANDO_GERENTE = "AGUARDANDO_GERENTE"
    AGUARDANDO_DIRETORIA = "AGUARDANDO_DIRETORIA"
    APROVADO = "APROVADO"
    AGUARDANDO_COMPRA = "AGUARDANDO_COMPRA"
    COMPRADO = "COMPRADO"
    RECEBIDO = "RECEBIDO"
    REJEITADO = "REJEITADO"
    CANCELADO = "CANCELADO"


class Pedido(Base, TenantMixin, AuditMixin, VersionMixin):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    status: Mapped[StatusPedido] = mapped_column(Enum(StatusPedido), default=StatusPedido.RASCUNHO, index=True)
    urgencia: Mapped[GrauUrgencia] = mapped_column(Enum(GrauUrgencia), default=GrauUrgencia.MEDIA, index=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    aprovador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    comprador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_estimado: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    itens = relationship("ItemPedido", back_populates="pedido", cascade="all, delete-orphan", lazy="selectin")
    historico = relationship("HistoricoPedido", back_populates="pedido", cascade="all, delete-orphan", lazy="selectin")


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    __table_args__ = (CheckConstraint("qtd_solicitada > 0", name="ck_item_qtd_positiva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"))
    qtd_solicitada: Mapped[float] = mapped_column(Numeric(14, 3))
    qtd_aprovada: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    qtd_comprada: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    custo_unitario: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    pedido = relationship("Pedido", back_populates="itens")
    material = relationship("Material")


class HistoricoPedido(Base):
    __tablename__ = "historico_pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), index=True)
    de_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    para_status: Mapped[str] = mapped_column(String(30))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    pedido = relationship("Pedido", back_populates="historico")
