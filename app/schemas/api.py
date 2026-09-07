from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..models.material import TipoMaterial
from ..models.pedido import GrauUrgencia, StatusPedido
from ..models.usuario import Papel

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class LoginResp(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_requerido: bool = False
    desafio_id: str | None = None


class MfaVerify(BaseModel):
    desafio_id: str
    codigo: str


class RefreshReq(BaseModel):
    refresh_token: str


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    papel: Papel
    limite_alcada: float = 0


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: EmailStr
    papel: Papel
    ativo: bool
    mfa_ativo: bool
    limite_alcada: float


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    papel: Papel | None = None
    ativo: bool | None = None
    senha: str | None = None
    limite_alcada: float | None = None


class MfaSetupOut(BaseModel):
    secret: str
    uri: str


class ClasseCreate(BaseModel):
    codigo: str
    nome: str


class ClasseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str


class MaterialCreate(BaseModel):
    codigo: str
    nome: str
    tipo: TipoMaterial
    unidade: str = "UN"
    classe_id: int
    estoque_minimo: float = 0
    custo_medio: float = 0


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str
    tipo: TipoMaterial
    unidade: str
    classe_id: int
    saldo_estoque: float
    saldo_reservado: float
    saldo_disponivel: float
    estoque_minimo: float
    custo_medio: float
    ativo: bool
    abaixo_do_minimo: bool


class ColaboradorCreate(BaseModel):
    matricula: str
    nome: str
    cargo: str | None = None
    centro_custo: str | None = None


class ColaboradorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    matricula: str
    nome: str
    cargo: str | None
    centro_custo: str | None
    ativo: bool


class ItemPedidoIn(BaseModel):
    material_id: int
    qtd_solicitada: float = Field(gt=0)


class PedidoCreate(BaseModel):
    urgencia: GrauUrgencia = GrauUrgencia.MEDIA
    justificativa: str | None = None
    itens: list[ItemPedidoIn] = Field(min_length=1)


class ItemAprovacao(BaseModel):
    item_id: int
    qtd_aprovada: float = Field(ge=0)


class AprovacaoGerente(BaseModel):
    itens: list[ItemAprovacao]
    observacao: str | None = None


class ItemCompra(BaseModel):
    item_id: int
    qtd_comprada: float = Field(ge=0)
    custo_unitario: float = Field(ge=0)


class EfetivarCompra(BaseModel):
    itens: list[ItemCompra]
    observacao: str | None = None


class ItemPedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    material_id: int
    qtd_solicitada: float
    qtd_aprovada: float | None
    qtd_comprada: float | None
    custo_unitario: float


class HistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    de_status: str | None
    para_status: str
    usuario_id: int
    observacao: str | None
    criado_em: datetime


class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: str
    status: StatusPedido
    urgencia: GrauUrgencia
    solicitante_id: int
    aprovador_id: int | None
    comprador_id: int | None
    justificativa: str | None
    valor_estimado: float
    itens: list[ItemPedidoOut]
    historico: list[HistoricoOut]


class BaixaQR(BaseModel):
    codigo_material: str
    quantidade: float = Field(gt=0, default=1)
    matricula: str | None = None
    observacao: str | None = None


class DevolucaoQR(BaseModel):
    comodato_id: int
    observacao: str | None = None


class EntradaEstoque(BaseModel):
    material_id: int
    quantidade: float = Field(gt=0)
    custo_unitario: float = Field(ge=0, default=0)
    observacao: str | None = None
