import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models.base import agora, garantir_aware
from ..models.usuario import Papel, Usuario
from ..schemas.api import LoginResp, MfaSetupOut, MfaVerify, RefreshReq, UsuarioCreate, UsuarioOut
from ..security import mfa as mfa_svc
from ..security.deps import CurrentUser, require_roles
from ..security.passwords import conferir_senha, hash_senha, validar_forca
from ..security.tokens import criar_access_token, decodificar, emitir_refresh_token, revogar, rotacionar_refresh
from ..services import audit_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])
settings = get_settings()

_desafios: dict[str, int] = {}


@router.post("/login", response_model=LoginResp)
async def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[AsyncSession, Depends(get_db)]):
    ip = request.client.host if request.client else None
    res = await db.execute(select(Usuario).where(Usuario.email == form.username))
    usuario = res.scalar_one_or_none()

    if usuario and usuario.bloqueado_ate and garantir_aware(usuario.bloqueado_ate) > agora():
        await audit_service.registrar(db, "login_bloqueado", "usuario", usuario.id, ip=ip)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Conta temporariamente bloqueada.")

    if not usuario or not conferir_senha(form.password, usuario.senha_hash):
        if usuario:
            usuario.tentativas_login += 1
            if usuario.tentativas_login >= settings.max_login_attempts:
                usuario.bloqueado_ate = agora() + timedelta(minutes=settings.lockout_minutes)
                usuario.tentativas_login = 0
            db.add(usuario)
            await audit_service.registrar(db, "login_falha", "usuario", usuario.id, ip=ip)
            await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo.")

    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    db.add(usuario)

    if usuario.mfa_ativo:
        desafio = uuid.uuid4().hex
        _desafios[desafio] = usuario.id
        await audit_service.registrar(db, "login_mfa_pendente", "usuario", usuario.id, ip=ip)
        return LoginResp(mfa_requerido=True, desafio_id=desafio)

    access = criar_access_token(usuario, mfa_ok=True)
    refresh = await emitir_refresh_token(db, usuario)
    await audit_service.registrar(db, "login_ok", "usuario", usuario.id, ip=ip)
    return LoginResp(access_token=access, refresh_token=refresh)


@router.post("/mfa/verify", response_model=LoginResp)
async def mfa_verify(dados: MfaVerify, db: Annotated[AsyncSession, Depends(get_db)]):
    uid = _desafios.get(dados.desafio_id)
    if not uid:
        raise HTTPException(status_code=400, detail="Desafio inválido ou expirado.")
    usuario = await db.get(Usuario, uid)
    if not usuario or not mfa_svc.verificar_codigo(usuario.mfa_secret, dados.codigo):
        raise HTTPException(status_code=401, detail="Código MFA inválido.")
    _desafios.pop(dados.desafio_id, None)
    access = criar_access_token(usuario, mfa_ok=True)
    refresh = await emitir_refresh_token(db, usuario)
    await audit_service.registrar(db, "mfa_ok", "usuario", usuario.id)
    return LoginResp(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=LoginResp)
async def refresh(dados: RefreshReq, db: Annotated[AsyncSession, Depends(get_db)]):
    resultado = await rotacionar_refresh(db, dados.refresh_token)
    if not resultado:
        raise HTTPException(status_code=401, detail="Refresh token inválido ou revogado.")
    access, novo_refresh = resultado
    return LoginResp(access_token=access, refresh_token=novo_refresh)


@router.post("/logout", status_code=204)
async def logout(dados: RefreshReq, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        payload = decodificar(dados.refresh_token)
        if payload.get("jti"):
            await revogar(db, payload["jti"])
    except Exception:
        pass


@router.get("/me", response_model=UsuarioOut)
async def me(usuario: CurrentUser):
    return usuario


@router.post("/mfa/setup", response_model=MfaSetupOut)
async def mfa_setup(usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    secret = mfa_svc.gerar_secret()
    usuario.mfa_secret = secret
    db.add(usuario)
    return MfaSetupOut(secret=secret, uri=mfa_svc.uri_provisionamento(secret, usuario.email))


@router.post("/mfa/ativar", status_code=204)
async def mfa_ativar(dados: MfaVerify, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if not mfa_svc.verificar_codigo(usuario.mfa_secret, dados.codigo):
        raise HTTPException(status_code=401, detail="Código MFA inválido.")
    usuario.mfa_ativo = True
    db.add(usuario)


@router.post("/usuarios", response_model=UsuarioOut, status_code=201, dependencies=[Depends(require_roles(Papel.DIRETOR))])
async def criar_usuario(dados: UsuarioCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    validar_forca(dados.senha)
    existe = await db.execute(select(Usuario).where(Usuario.email == dados.email))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")
    usuario = Usuario(
        nome=dados.nome, email=dados.email, senha_hash=hash_senha(dados.senha), papel=dados.papel, limite_alcada=dados.limite_alcada
    )
    db.add(usuario)
    await db.flush()
    await db.refresh(usuario)
    return usuario
