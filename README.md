# GWI Materiais — Backend v2 (Enterprise Hardened)

Evolução enterprise do módulo de Gestão de Materiais, com foco em **segurança, integridade de dados e testabilidade**. Toda a camada abaixo está **implementada e testada** (23 testes, incluindo testes contra ataque).

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m app.seed          # popula usuários, classes, materiais, colaboradores
uvicorn app.main:app --reload
```

Testes:

```bash
python -m pytest -v
```

## Usuários de demonstração

Senha para todos: `Gramo@Forte2026!`

| Perfil | E-mail | Aprovação |
|---|---|---|
| Almoxarife | almoxarife@gramo.com | — |
| ADM/Compras | compras@gramo.com | — |
| Gerente | gerente@gramo.com | Aprova todos os pedidos |

---

## O que está implementado e testado

### Segurança
- **Autenticação JWT** com access token curto (15 min) + **refresh token com rotação e revogação**, com detecção de reuso (revoga a cadeia inteira se um refresh já usado é reapresentado).
- **MFA (TOTP)** compatível com Google Authenticator/Authy — setup, ativação e verificação no login.
- **Proteção contra brute force:** bloqueio de conta após N tentativas, com persistência garantida do contador mesmo em falha.
- **Rate limiting** por IP (limite separado para login).
- **Política de senha forte** (12+ caracteres, maiúscula, minúscula, número, símbolo).
- **RBAC por perfil:** cada perfil só executa o que lhe cabe; o gerente é o aprovador único e aprova todos os pedidos encaminhados.
- **Security headers** (HSTS, CSP, X-Frame-Options, nosniff, no-store) e header `Server` removido.
- **Tratamento global de erros** que nunca vaza stack trace, SQL ou caminho de arquivo.
- **CORS restrito** por origem, método e header. Documentação (`/docs`) desativada em produção.

### Integridade de dados
- **Kardex append-only com hash encadeado (SHA-256):** cada movimentação encadeia no hash da anterior; adulteração é detectável via endpoint de verificação de integridade.
- **Reserva de saldo na aprovação** + **saldo disponível** = saldo − reservado, impedindo que dois pedidos consumam o mesmo estoque.
- **Locking otimista** (coluna `version`) nas entidades críticas.
- **Idempotência** via header `Idempotency-Key` — replay/duplo-clique não duplica operação.
- **Constraints no banco** (CHECK de saldo ≥ 0, quantidade > 0) como última linha de defesa.
- **Custo médio ponderado** em `Decimal` (nunca float).
- **Trilha de auditoria** (quem/quando/o quê) nas ações sensíveis.

### Observabilidade
- **Logs estruturados JSON** com `request_id` (correlation) propagado por toda a request.
- **Health checks** `/health/live` e `/health/ready`.

### Cobertura de testes (23 casos)
Fluxo de negócio completo · autenticação (sem token / inválido / adulterado) · autorização por perfil (bypass → 403) · brute force → lockout · injeção SQL (4 payloads) · não-vazamento de stack trace · security headers · aprovação do gerente · idempotência · reserva de saldo · MFA (fluxo completo com TOTP real) · rotação e revogação de refresh · senha fraca · comodato · integridade do kardex.

---

## O que NÃO está aqui — e por quê

Estes itens do roadmap **dependem de infraestrutura ou credenciais externas** que não existem em ambiente de desenvolvimento. Não é questão de código faltando; é que "funcionar" exige o ambiente real da empresa:

- **SSO real (Azure AD / Google Workspace):** o código de auth já é OIDC-friendly, mas exige o tenant e as credenciais corporativas da GRAMO para conectar. Hoje entregamos JWT+MFA próprios; a troca por SSO é ponto de integração, não reescrita.
- **Integração ERP (SAP/TOTVS) e fiscal (NF-e/SPED):** exige ambiente, contrato e credenciais do ERP da empresa.
- **Redis / RabbitMQ / Celery:** o rate limiting e a idempotência hoje usam banco/memória; em produção migram para Redis (troca de backend, lógica já isolada). Filas exigem broker provisionado.
- **Kubernetes, Terraform, CI/CD, DR multi-região:** infraestrutura de nuvem a provisionar.
- **Pentest e testes de carga (k6):** exigem ambiente dedicado e ferramentas externas; a suíte automatizada já cobre a superfície de aplicação.

A camada de aplicação — a parte que **é** código e **pode** ser testada — está pronta e verde. As próximas fases são de integração e infraestrutura.

## Nota sobre comentários no código

O código não tem comentários, conforme solicitado. Vale registrar, para clareza técnica: comentário em código de **backend** não é vetor de ataque — o fonte do servidor não é servido ao cliente. Os vetores reais de vazamento de informação **foram tratados**: nenhum stack trace, SQL ou caminho de arquivo aparece em resposta de erro; o header `Server` é removido; e a documentação da API é desativada em produção.
