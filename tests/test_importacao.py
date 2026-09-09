from decimal import Decimal

import pytest

from app.services.importacao import ler_planilha, parse_valor_br, valor_por_sinonimo
from .conftest import hdr

pytestmark = pytest.mark.asyncio


def test_parse_valor_br():
    assert parse_valor_br("R$ 1.234,56") == Decimal("1234.56")
    assert parse_valor_br("1.234,56") == Decimal("1234.56")
    assert parse_valor_br("1234,56") == Decimal("1234.56")
    assert parse_valor_br("1234.56") == Decimal("1234.56")
    assert parse_valor_br("") is None
    assert parse_valor_br("abc") is None
    assert parse_valor_br(1234.5) == Decimal("1234.50")


def test_ler_planilha_formato_invalido():
    with pytest.raises(ValueError):
        ler_planilha(b"qualquer", "arquivo.pdf")


def test_ler_planilha_vazia():
    with pytest.raises(ValueError):
        ler_planilha(b"", "a.csv")


def test_ler_csv_latin1_e_sinonimo():
    conteudo = "nome;matricula\nJosé Antônio;99\n".encode("latin-1")
    regs = ler_planilha(conteudo, "a.csv")
    assert regs[0]["dados"]["nome"] == "José Antônio"
    assert valor_por_sinonimo(regs[0]["dados"], ["inexistente", "matricula"]) == "99"
    assert valor_por_sinonimo(regs[0]["dados"], ["nao_tem"]) == ""


def _csv(texto: str):
    return {"arquivo": ("planilha.csv", texto.encode("utf-8"), "text/csv")}


async def test_preview_colaboradores_identifica_erros(client):
    h = await hdr(client, "compras@g.com")
    csv = "nome;matricula\nJoao Silva;10001\n;10002\nMaria Souza;10003\n"
    r = await client.post("/colaboradores/importar/preview", headers=h, files=_csv(csv))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["criar"] == 2
    assert body["erros"] == 1
    erro = next(l for l in body["linhas"] if l["acao"] == "erro")
    assert erro["linha"] == 3


async def test_confirmar_colaboradores_grava(client):
    h = await hdr(client, "compras@g.com")
    csv = "nome;matricula\nAna Lima;20001\nBruno Dias;20002\n"
    r = await client.post("/colaboradores/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "false"})
    assert r.status_code == 200
    assert r.json()["criados"] == 2

    r = await client.get("/colaboradores?busca=20001", headers=h)
    assert r.json()["total"] == 1


async def test_confirmar_bloqueia_com_erro_sem_ignorar(client):
    h = await hdr(client, "compras@g.com")
    csv = "nome;matricula\n;30001\n"
    r = await client.post("/colaboradores/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "false"})
    assert r.status_code == 422


async def test_confirmar_colaboradores_ignorando_erros(client):
    h = await hdr(client, "compras@g.com")
    csv = "nome;matricula\nValido Um;31001\n;31002\n"
    r = await client.post("/colaboradores/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "true"})
    assert r.status_code == 200
    body = r.json()
    assert body["criados"] == 1
    assert body["rejeitados"] == 1


async def test_confirmar_colaboradores_atualiza_existente(client):
    h = await hdr(client, "compras@g.com")
    csv = "nome;matricula\nJoao Atualizado;00123\n"
    r = await client.post("/colaboradores/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "false"})
    assert r.status_code == 200
    assert r.json()["atualizados"] == 1


async def test_import_materiais_valor_brasileiro(client):
    h = await hdr(client, "compras@g.com")
    csv = "codigo;nome;classe;unidade;custo;estoque_minimo\nMAT-NEW;Cabo flexivel;Abrasivos;m;1.234,56;50\n"
    r = await client.post("/materiais/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "false"})
    assert r.status_code == 200
    assert r.json()["criados"] == 1

    r = await client.get("/materiais?busca=MAT-NEW", headers=h)
    item = r.json()["items"][0]
    assert float(item["custo_medio"]) == 1234.56


async def test_import_materiais_classe_inexistente_vira_erro(client):
    h = await hdr(client, "compras@g.com")
    csv = "codigo;nome;classe;unidade;custo\nMAT-X;Item;ClasseFantasma;UN;10,00\n"
    r = await client.post("/materiais/importar/preview", headers=h, files=_csv(csv))
    assert r.status_code == 200
    assert r.json()["erros"] == 1


async def test_modelo_xlsx_disponivel(client):
    h = await hdr(client, "compras@g.com")
    r = await client.get("/materiais/importar/modelo", headers=h)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # assinatura de arquivo .xlsx (zip)


async def test_permissao_almoxarife_nao_importa_material(client):
    h = await hdr(client, "almox@g.com")
    csv = "codigo;nome;classe\nMAT-Z;Item;Abrasivos\n"
    r = await client.post("/materiais/importar/preview", headers=h, files=_csv(csv))
    assert r.status_code == 403


async def test_modelo_colaboradores_disponivel(client):
    h = await hdr(client, "compras@g.com")
    r = await client.get("/colaboradores/importar/modelo", headers=h)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


async def test_import_colaboradores_via_xlsx(client):
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["nome", "matricula"])
    ws.append(["Carlos Xls", "40001"])
    ws.append(["Diana Xls", "40002"])
    buf = BytesIO()
    wb.save(buf)

    files = {"arquivo": ("colabs.xlsx", buf.getvalue(),
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    h = await hdr(client, "compras@g.com")
    r = await client.post("/colaboradores/importar/confirmar", headers=h, files=files, data={"ignorar_erros": "false"})
    assert r.status_code == 200
    assert r.json()["criados"] == 2
    assert r.json()["relatorio_xlsx_base64"]


async def test_import_materiais_ignorar_erros_grava_validos(client):
    h = await hdr(client, "compras@g.com")
    csv = ("codigo;nome;classe;unidade;custo\n"
           "MAT-OK;Item bom;Abrasivos;UN;10,00\n"
           "MAT-BAD;Item ruim;ClasseFantasma;UN;5,00\n")
    r = await client.post("/materiais/importar/confirmar", headers=h, files=_csv(csv), data={"ignorar_erros": "true"})
    assert r.status_code == 200
    body = r.json()
    assert body["criados"] == 1
    assert body["rejeitados"] == 1
