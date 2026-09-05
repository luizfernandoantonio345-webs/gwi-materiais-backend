from sqlalchemy.ext.asyncio import AsyncSession

from ..models.seguranca import AuditLog


async def registrar(
    db: AsyncSession,
    acao: str,
    entidade: str,
    usuario_id: int | None = None,
    entidade_id: str | None = None,
    detalhe: str | None = None,
    ip: str | None = None,
) -> None:
    db.add(AuditLog(usuario_id=usuario_id, acao=acao, entidade=entidade, entidade_id=entidade_id, detalhe=detalhe, ip=ip))
