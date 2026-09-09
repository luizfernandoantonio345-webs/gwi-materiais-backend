import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import AuditMixin, TenantMixin


class Papel(str, enum.Enum):
    ALMOXARIFE = "ALMOXARIFE"
    ADM_COMPRAS = "ADM_COMPRAS"
    GERENTE = "GERENTE"


class Usuario(Base, TenantMixin, AuditMixin):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    foto: Mapped[str | None] = mapped_column(Text, nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    papel: Mapped[Papel] = mapped_column(Enum(Papel), index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    limite_alcada: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_backup_codes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tentativas_login: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
