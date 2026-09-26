<div align="center">

# GWI Materiais — API

**Gestão de materiais e almoxarifado para obras industriais**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2_async-D71F00?logo=sqlalchemy&logoColor=white)
![Tests](https://img.shields.io/badge/testes-62-22D3A6)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

[**Demo**](https://gwi-frontend.vercel.app) · [Frontend](https://github.com/luizfernandoantonio345-webs/gwi-frontend) · [Segurança](SECURITY.md)

</div>

---

Backend do módulo de materiais da plataforma GWI, desenvolvido para a **GRAMO Engenharia** para substituir
o controle manual do almoxarifado de obra. Cobre o ciclo completo: cadastro, requisição, aprovação por alçada,
compra, entrada em estoque, baixa por QR Code e comodato de ferramentas — com rastreabilidade de cada movimentação.

## Destaques de engenharia

| | |
|---|---|
| **Kardex à prova de adulteração** | Movimentações append-only encadeadas por hash SHA-256; endpoint de verificação detecta qualquer alteração retroativa |
| **Estoque sem condição de corrida** | Reserva de saldo na aprovação, locking otimista (`version`) e `CHECK` no banco impedem que dois pedidos consumam o mesmo item |
| **Dinheiro em `Decimal`** | Custo médio ponderado sem erro de ponto flutuante |
| **Autenticação robusta** | JWT de 15 min + refresh token com rotação e **detecção de reuso** (revoga a cadeia inteira), MFA TOTP com códigos de backup |
| **Defesa em profundidade** | RBAC + alçada por valor, bloqueio por força bruta, rate limit por IP, security headers, erros que nunca vazam stack trace |
| **Tempo real** | WebSocket autenticado para notificar aprovações e compras por perfil |
| **Observabilidade** | Logs JSON estruturados com `request_id` propagado; health checks `live` / `ready` |

## Arquitetura

```
app/
├── routers/      # auth, catálogo, pedidos, operações, requisições (45 endpoints)
├── services/     # regras de negócio: estoque, workflow de aprovação, importação .xlsx, auditoria
├── models/       # SQLAlchemy 2.0 async — materiais, estoque/kardex, pedidos, comodato, usuários
├── security/     # tokens, MFA, senhas, dependências de RBAC, middlewares
└── realtime.py   # gerenciador de conexões WebSocket por perfil
alembic/          # migrações versionadas
tests/            # 62 testes: fluxo de negócio + testes de ataque
```

Camadas separadas (router → service → model): as rotas só validam entrada e permissão; toda regra de estoque
vive em `services/`, testável sem HTTP.

## Fluxo principal

```
Almoxarife cria requisição ─► Gerente aprova (alçada) ─► saldo reservado
        │                                                     │
        ▼                                                     ▼
  sem estoque ─► fila de compra ─► entrada em estoque ─► baixa por QR (crachá + material)
                                                               │
                                                               ▼
                                              kardex encadeado + trilha de auditoria
```

## Testes

62 testes automatizados, incluindo cenários de ataque:

- bypass de autorização por perfil → `403`
- força bruta → bloqueio de conta
- injeção SQL (múltiplos payloads) e token adulterado
- replay de refresh token → revogação da cadeia
- MFA com TOTP real, idempotência, integridade do kardex, importação de planilha

```bash
python -m pytest -v --cov=app
```

A suíte roda em SQLite (rápido) e em **PostgreSQL 16** — bugs de timezone e de event loop do driver
assíncrono só apareceram contra o Postgres real.

## Rodando localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # defina SECRET_KEY: openssl rand -hex 32

alembic upgrade head
python -m app.seed              # dados de demonstração
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Ou com Docker (API + PostgreSQL + Redis):

```bash
docker compose up --build
```

**Usuários de demonstração** (criados pelo seed): `almoxarife@gramo.com`, `compras@gramo.com`,
`gerente@gramo.com` — senha definida em `app/seed.py`. Troque as senhas em qualquer ambiente real.

## Deploy

`render.yaml` provisiona API + PostgreSQL no Render, com `SECRET_KEY` gerada pela plataforma e migrações
aplicadas no start. O frontend é servido pela Vercel.

## Roadmap

Itens que dependem da infraestrutura do cliente, não de código:

- SSO corporativo (Azure AD / Google Workspace) — a autenticação já é compatível com OIDC
- Integração com ERP (SAP / TOTVS) e NF-e
- Rate limit e idempotência em Redis (lógica já isolada; hoje em banco/memória)
- Pipeline de CI no GitHub Actions — ver [CI.md](CI.md)

---

<sub>Desenvolvido por <a href="https://github.com/luizfernandoantonio345-webs">Luiz Fernando</a> para a GRAMO Engenharia.</sub>
