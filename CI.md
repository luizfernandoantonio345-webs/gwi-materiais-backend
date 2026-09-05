# CI/CD — Pipeline de Integração Contínua

Dois workflows do GitHub Actions rodam a cada push e pull request, garantindo que nada quebre.

## Backend (`.github/workflows/ci-backend.yml`)

| Job | O que faz | Falha se… |
|---|---|---|
| **lint** | `ruff check` + `ruff format --check` | há erro de lint ou formatação fora do padrão |
| **test-sqlite** | Suíte completa (27 testes) + cobertura (gate 70%) em SQLite | qualquer teste falha |
| **test-postgres** | Mesma suíte (27 testes) contra PostgreSQL 16 real (service container) | qualquer teste falha |
| **migrations** | `alembic upgrade head` → `downgrade base` → `upgrade head` em Postgres | migração não aplica/reverte |
| **security** | `bandit` (SAST, falha em severidade média+) + `pip-audit` (CVEs em dependências) | vulnerabilidade média+ ou dependência com CVE |
| **docker** | `docker build` da imagem de produção | build da imagem falha |

O job `docker` só roda depois de `lint` e `test-sqlite` passarem.

### Por que testar em SQLite **e** Postgres?

Bugs dependentes de banco só aparecem no Postgres. Durante o desenvolvimento, um bug de comparação de datas (naive vs aware) e um problema de event loop do driver assíncrono passaram despercebidos no SQLite e só foram pegos ao rodar contra Postgres. Rodar nos dois é a rede de proteção.

## Frontend (`.github/workflows/ci-frontend.yml`)

| Job | O que faz | Falha se… |
|---|---|---|
| **build** | Bundle do cliente de API e do app via esbuild | erro de sintaxe/import em qualquer arquivo |

## Gatilhos

- Push em `main` e `develop`.
- Pull requests.
- Execução manual (`workflow_dispatch`).
- Filtro por caminho: mudanças no backend só disparam o CI do backend, e vice-versa.

## Validação local já realizada

Antes de entregar, todos os jobs foram simulados neste ambiente e passaram:

- `ruff check` e `ruff format --check`: limpos.
- Suíte de 23 testes: verde em **SQLite e em PostgreSQL 16 real**.
- Migrações Alembic: upgrade/downgrade/upgrade em Postgres real.
- `bandit` (média+) e `pip-audit`: sem apontamentos.
- Bundle do frontend: sem erros.

## Próximos passos naturais do pipeline (fora do escopo de código)

- Push da imagem para um registry (GHCR/ECR) com tag por commit — exige credenciais do registry.
- Deploy automático em staging após o verde na `main` — exige o ambiente de destino provisionado.
- Cobertura de testes publicada (coverage + badge) — trivial de plugar com `pytest-cov`.
