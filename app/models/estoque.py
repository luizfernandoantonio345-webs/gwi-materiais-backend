import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TenantMixin, agora


class TipoMovimento(str, enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    DEVOLUCAO = "DEVOLUCAO"
    AJUSTE = "AJUSTE"


class MovimentacaoEstoque(Base, TenantMixin):
    __tablename__ = "movimentacoes_estoque"
    __table_args__ = (CheckConstraint("quantidade > 0", name="ck_mov_qtd_positiva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"), index=True)
    tipo: Mapped[TipoMovimento] = mapped_column(Enum(TipoMovimento))
    quantidade: Mapped[float] = mapped_column(Numeric(14, 3))
    custo_unitario: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    saldo_apos: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    colaborador_id: Mapped[int | None] = mapped_column(ForeignKey("colaboradores.id"), nullable=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    observacao: Mapped[str | None] = mapped_column(String(240), nullable=True)
    hash_anterior: Mapped[str] = mapped_column(String(64), default="")
    hash_atual: Mapped[str] = mapped_column(String(64), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class StatusComodato(str, enum.Enum):
    ABERTO = "ABERTO"
    DEVOLVIDO = "DEVOLVIDO"
    BAIXADO_PERDA = "BAIXADO_PERDA"


class Comodato(Base, TenantMixin):
    __tablename__ = "comodatos"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"), index=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    quantidade: Mapped[float] = mapped_column(Numeric(14, 3), default=1)
    status: Mapped[StatusComodato] = mapped_column(Enum(StatusComodato), default=StatusComodato.ABERTO, index=True)
    retirado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    devolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    almoxarife_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    material = relationship("Material")
    colaborador = relationship("Colaborador")
