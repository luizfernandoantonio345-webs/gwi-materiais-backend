from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


def agora() -> datetime:
    return datetime.now(UTC)


def garantir_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AuditMixin:
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    criado_por: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)
    atualizado_por: Mapped[int | None] = mapped_column(Integer, nullable=True)


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TenantMixin:
    tenant: Mapped[str] = mapped_column(String(50), index=True, default="GRAMO")
