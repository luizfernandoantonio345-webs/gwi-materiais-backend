import enum

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import AuditMixin, TenantMixin, VersionMixin


class Colaborador(Base, TenantMixin, AuditMixin):
    __tablename__ = "colaboradores"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    centro_custo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class TipoMaterial(str, enum.Enum):
    CONSUMIVEL = "CONSUMIVEL"
    FERRAMENTA = "FERRAMENTA"
    EPI = "EPI"


class ClasseMaterial(Base, TenantMixin):
    __tablename__ = "classes_material"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    materiais = relationship("Material", back_populates="classe")


class Material(Base, TenantMixin, AuditMixin, VersionMixin):
    __tablename__ = "materiais"
    __table_args__ = (
        CheckConstraint("saldo_estoque >= 0", name="ck_saldo_nao_negativo"),
        CheckConstraint("saldo_reservado >= 0", name="ck_reservado_nao_negativo"),
        CheckConstraint("estoque_minimo >= 0", name="ck_minimo_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(160))
    tipo: Mapped[TipoMaterial] = mapped_column(Enum(TipoMaterial), index=True)
    unidade: Mapped[str] = mapped_column(String(10), default="UN")
    classe_id: Mapped[int] = mapped_column(ForeignKey("classes_material.id"))

    saldo_estoque: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    saldo_reservado: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    estoque_minimo: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    custo_medio: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    classe = relationship("ClasseMaterial", back_populates="materiais")

    @property
    def saldo_disponivel(self) -> float:
        return float(self.saldo_estoque) - float(self.saldo_reservado)

    @property
    def abaixo_do_minimo(self) -> bool:
        return float(self.saldo_estoque) <= float(self.estoque_minimo)
