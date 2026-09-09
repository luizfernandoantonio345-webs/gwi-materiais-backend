import base64
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.colaborador import Colaborador
from ..models.material import ClasseMaterial, Material, TipoMaterial
from ..models.usuario import Papel
from ..schemas.api import (
    ClasseCreate,
    ClasseOut,
    ColaboradorCreate,
    ColaboradorOut,
    LinhaImportacao,
    MaterialCreate,
    MaterialOut,
    Pagina,
    PreviewImportacao,
    ResultadoImportacao,
)
from ..security.deps import CurrentUser, require_roles
from ..services import audit_service
from ..services.importacao import (
    gerar_modelo_xlsx,
    gerar_relatorio_xlsx,
    ler_planilha,
    normalizar_chave,
    parse_valor_br,
    valor_por_sinonimo,
)

router = APIRouter(tags=["Catálogo"])
somente_adm = require_roles(Papel.ADM_COMPRAS)
adm_ou_almox = require_roles(Papel.ADM_COMPRAS, Papel.ALMOXARIFE)

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


async def _contar(db: AsyncSession, stmt) -> int:
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    return int(total or 0)


@router.post("/classes", response_model=ClasseOut, status_code=201, dependencies=[Depends(somente_adm)])
async def criar_classe(dados: ClasseCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    classe = ClasseMaterial(**dados.model_dump())
    db.add(classe)
    await db.flush()
    await db.refresh(classe)
    return classe


@router.get("/classes", response_model=Pagina[ClasseOut])
async def listar_classes(_: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)], limit: Limit = 50, offset: Offset = 0):
    base = select(ClasseMaterial).order_by(ClasseMaterial.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    return Pagina(items=list(res.scalars().all()), total=total, limit=limit, offset=offset)


@router.post("/materiais", response_model=MaterialOut, status_code=201, dependencies=[Depends(somente_adm)])
async def criar_material(dados: MaterialCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    if not await db.get(ClasseMaterial, dados.classe_id):
        raise HTTPException(status_code=404, detail="Classe não encontrada.")
    existe = await db.execute(select(Material).where(Material.codigo == dados.codigo))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Código já existe.")
    material = Material(**dados.model_dump())
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return material


@router.get("/materiais", response_model=Pagina[MaterialOut])
async def listar_materiais(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    abaixo_minimo: bool = False,
    busca: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    base = select(Material).where(Material.ativo.is_(True))
    if busca:
        termo = f"%{busca.strip()}%"
        base = base.where(or_(Material.nome.ilike(termo), Material.codigo.ilike(termo)))
    base = base.order_by(Material.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    itens = list(res.scalars().all())
    if abaixo_minimo:
        itens = [m for m in itens if m.abaixo_do_minimo]
    return Pagina(items=itens, total=total, limit=limit, offset=offset)


@router.post(
    "/colaboradores",
    response_model=ColaboradorOut,
    status_code=201,
    dependencies=[Depends(require_roles(Papel.ADM_COMPRAS, Papel.ALMOXARIFE))],
)
async def criar_colaborador(dados: ColaboradorCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existe = await db.execute(select(Colaborador).where(Colaborador.matricula == dados.matricula))
    if existe.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Matrícula já cadastrada.")
    colab = Colaborador(**dados.model_dump())
    db.add(colab)
    await db.flush()
    await db.refresh(colab)
    return colab


@router.get("/colaboradores", response_model=Pagina[ColaboradorOut])
async def listar_colaboradores(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    busca: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    base = select(Colaborador)
    if busca:
        termo = f"%{busca.strip()}%"
        base = base.where(or_(Colaborador.nome.ilike(termo), Colaborador.matricula.ilike(termo)))
    base = base.order_by(Colaborador.nome)
    total = await _contar(db, base)
    res = await db.execute(base.limit(limit).offset(offset))
    return Pagina(items=list(res.scalars().all()), total=total, limit=limit, offset=offset)


# ─────────────────────────────────────────────────────────────
# Importação por planilha (colaboradores e materiais)
# ─────────────────────────────────────────────────────────────

def _pub(linhas: list[dict]) -> list[LinhaImportacao]:
    return [LinhaImportacao(linha=x["linha"], acao=x["acao"], dados=x["dados"], erro=x["erro"]) for x in linhas]


def _preview(linhas: list[dict]) -> PreviewImportacao:
    return PreviewImportacao(
        total=len(linhas),
        criar=sum(1 for x in linhas if x["acao"] == "criar"),
        atualizar=sum(1 for x in linhas if x["acao"] == "atualizar"),
        erros=sum(1 for x in linhas if x["acao"] == "erro"),
        linhas=_pub(linhas),
    )


def _resultado(linhas: list[dict], criados: int, atualizados: int) -> ResultadoImportacao:
    rel = gerar_relatorio_xlsx(linhas)
    return ResultadoImportacao(
        criados=criados,
        atualizados=atualizados,
        rejeitados=sum(1 for x in linhas if x["acao"] == "erro"),
        linhas=_pub(linhas),
        relatorio_xlsx_base64=base64.b64encode(rel).decode(),
    )


async def _ler(arquivo: UploadFile) -> list[dict]:
    try:
        return ler_planilha(await arquivo.read(), arquivo.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _analisar_colaboradores(registros: list[dict], db: AsyncSession) -> list[dict]:
    res = await db.execute(select(Colaborador.matricula))
    existentes = {m for (m,) in res.all()}
    vistos: set[str] = set()
    linhas: list[dict] = []
    for reg in registros:
        d = reg["dados"]
        nome = valor_por_sinonimo(d, ["nome", "nome_completo"])
        matricula = valor_por_sinonimo(d, ["matricula", "matricula_funcional", "mat"])
        cargo = valor_por_sinonimo(d, ["cargo", "funcao", "cargo_funcao", "cargo/funcao"])
        centro = valor_por_sinonimo(d, ["centro_de_custo", "centro_custo", "centrocusto", "centro"])
        display = {"nome": nome, "matricula": matricula, "cargo": cargo, "centro_custo": centro}
        erro = None
        if not nome or not matricula:
            erro = "Nome e matrícula são obrigatórios."
        elif matricula in vistos:
            erro = "Matrícula duplicada na planilha."
        if erro:
            acao = "erro"
        else:
            vistos.add(matricula)
            acao = "atualizar" if matricula in existentes else "criar"
        linhas.append({
            "linha": reg["linha"], "acao": acao, "dados": display, "erro": erro,
            "_p": {"nome": nome, "matricula": matricula, "cargo": cargo or None, "centro_custo": centro or None},
        })
    return linhas


async def _commit_colaboradores(linhas: list[dict], db: AsyncSession) -> tuple[int, int]:
    criados = atualizados = 0
    for item in linhas:
        if item["acao"] == "erro":
            continue
        p = item["_p"]
        atual = (await db.execute(select(Colaborador).where(Colaborador.matricula == p["matricula"]))).scalar_one_or_none()
        if atual:
            atual.nome = p["nome"]
            if p["cargo"] is not None:
                atual.cargo = p["cargo"]
            if p["centro_custo"] is not None:
                atual.centro_custo = p["centro_custo"]
            db.add(atual)
            atualizados += 1
        else:
            db.add(Colaborador(**p))
            criados += 1
    return criados, atualizados


async def _analisar_materiais(registros: list[dict], db: AsyncSession) -> list[dict]:
    classes = (await db.execute(select(ClasseMaterial))).scalars().all()
    mapa = {}
    for c in classes:
        mapa[normalizar_chave(c.nome)] = c.id
        mapa[c.codigo.strip().lower()] = c.id
    res = await db.execute(select(Material.codigo))
    existentes = {c for (c,) in res.all()}
    vistos: set[str] = set()
    linhas: list[dict] = []
    for reg in registros:
        d = reg["dados"]
        codigo = valor_por_sinonimo(d, ["codigo", "codigo_interno", "cod", "codigo_do_material"])
        nome = valor_por_sinonimo(d, ["nome", "descricao", "descricao_do_material", "material"])
        classe_txt = valor_por_sinonimo(d, ["classe", "categoria", "classe_categoria"])
        unidade = valor_por_sinonimo(d, ["unidade", "unidade_de_medida", "un"]) or "UN"
        tipo_txt = valor_por_sinonimo(d, ["tipo"]).upper()
        custo = parse_valor_br(valor_por_sinonimo(d, ["valor_unitario", "custo", "valor", "preco", "custo_medio"]))
        emin = parse_valor_br(valor_por_sinonimo(d, ["estoque_minimo", "minimo", "estoque_min"]))
        display = {
            "codigo": codigo, "nome": nome, "classe": classe_txt, "unidade": unidade,
            "custo": str(custo) if custo is not None else "", "estoque_minimo": str(emin) if emin is not None else "",
        }
        erro = None
        classe_id = None
        tipo_val = "CONSUMIVEL"
        if not codigo or not nome:
            erro = "Código e nome são obrigatórios."
        elif codigo in vistos:
            erro = "Código duplicado na planilha."
        elif tipo_txt and tipo_txt not in TipoMaterial.__members__:
            erro = f"Tipo inválido: {tipo_txt}."
        elif not classe_txt:
            erro = "Classe é obrigatória."
        else:
            classe_id = mapa.get(normalizar_chave(classe_txt)) or mapa.get(classe_txt.strip().lower())
            if not classe_id:
                erro = f"Classe não encontrada: {classe_txt}."
        if tipo_txt in TipoMaterial.__members__:
            tipo_val = tipo_txt
        if erro:
            acao = "erro"
        else:
            vistos.add(codigo)
            acao = "atualizar" if codigo in existentes else "criar"
        linhas.append({
            "linha": reg["linha"], "acao": acao, "dados": display, "erro": erro,
            "_p": {"codigo": codigo, "nome": nome, "tipo": tipo_val, "unidade": unidade,
                   "classe_id": classe_id, "custo_medio": custo, "estoque_minimo": emin},
        })
    return linhas


async def _commit_materiais(linhas: list[dict], db: AsyncSession) -> tuple[int, int]:
    criados = atualizados = 0
    for item in linhas:
        if item["acao"] == "erro":
            continue
        p = item["_p"]
        atual = (await db.execute(select(Material).where(Material.codigo == p["codigo"]))).scalar_one_or_none()
        if atual:
            atual.nome = p["nome"]
            atual.tipo = TipoMaterial[p["tipo"]]
            atual.unidade = p["unidade"]
            atual.classe_id = p["classe_id"]
            if p["custo_medio"] is not None:
                atual.custo_medio = p["custo_medio"]
            if p["estoque_minimo"] is not None:
                atual.estoque_minimo = p["estoque_minimo"]
            db.add(atual)
            atualizados += 1
        else:
            db.add(Material(
                codigo=p["codigo"], nome=p["nome"], tipo=TipoMaterial[p["tipo"]], unidade=p["unidade"],
                classe_id=p["classe_id"], custo_medio=p["custo_medio"] or 0, estoque_minimo=p["estoque_minimo"] or 0,
            ))
            criados += 1
    return criados, atualizados


@router.get("/colaboradores/importar/modelo", dependencies=[Depends(adm_ou_almox)])
async def modelo_colaboradores():
    conteudo = gerar_modelo_xlsx(
        "Colaboradores", ["nome", "matricula", "cargo", "centro_custo"],
        ["João da Silva", "00123", "Eletricista", "OBRA-01"],
    )
    return Response(content=conteudo, media_type=XLSX_MEDIA,
                    headers={"Content-Disposition": "attachment; filename=modelo_colaboradores.xlsx"})


@router.post("/colaboradores/importar/preview", response_model=PreviewImportacao, dependencies=[Depends(adm_ou_almox)])
async def preview_colaboradores(db: Annotated[AsyncSession, Depends(get_db)], arquivo: UploadFile = File(...)):
    return _preview(await _analisar_colaboradores(await _ler(arquivo), db))


@router.post("/colaboradores/importar/confirmar", response_model=ResultadoImportacao, dependencies=[Depends(adm_ou_almox)])
async def confirmar_colaboradores(
    usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)],
    arquivo: UploadFile = File(...), ignorar_erros: bool = Form(False),
):
    linhas = await _analisar_colaboradores(await _ler(arquivo), db)
    if any(x["acao"] == "erro" for x in linhas) and not ignorar_erros:
        raise HTTPException(status_code=422, detail="Há linhas com erro. Corrija a planilha ou marque 'ignorar linhas com erro'.")
    criados, atualizados = await _commit_colaboradores(linhas, db)
    await audit_service.registrar(db, "colaboradores_importados", "colaborador", usuario.id,
                                  f"{criados} criados, {atualizados} atualizados")
    return _resultado(linhas, criados, atualizados)


@router.get("/materiais/importar/modelo", dependencies=[Depends(somente_adm)])
async def modelo_materiais():
    conteudo = gerar_modelo_xlsx(
        "Materiais", ["codigo", "nome", "classe", "unidade", "custo", "estoque_minimo", "tipo"],
        ["MAT-001", "Cabo flexível 2,5mm", "Elétrico", "m", "1.234,56", "50", "CONSUMIVEL"],
    )
    return Response(content=conteudo, media_type=XLSX_MEDIA,
                    headers={"Content-Disposition": "attachment; filename=modelo_materiais.xlsx"})


@router.post("/materiais/importar/preview", response_model=PreviewImportacao, dependencies=[Depends(somente_adm)])
async def preview_materiais(db: Annotated[AsyncSession, Depends(get_db)], arquivo: UploadFile = File(...)):
    return _preview(await _analisar_materiais(await _ler(arquivo), db))


@router.post("/materiais/importar/confirmar", response_model=ResultadoImportacao, dependencies=[Depends(somente_adm)])
async def confirmar_materiais(
    usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)],
    arquivo: UploadFile = File(...), ignorar_erros: bool = Form(False),
):
    linhas = await _analisar_materiais(await _ler(arquivo), db)
    if any(x["acao"] == "erro" for x in linhas) and not ignorar_erros:
        raise HTTPException(status_code=422, detail="Há linhas com erro. Corrija a planilha ou marque 'ignorar linhas com erro'.")
    criados, atualizados = await _commit_materiais(linhas, db)
    await audit_service.registrar(db, "materiais_importados", "material", usuario.id,
                                  f"{criados} criados, {atualizados} atualizados")
    return _resultado(linhas, criados, atualizados)
