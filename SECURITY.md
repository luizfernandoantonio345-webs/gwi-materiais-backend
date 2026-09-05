# Política de Segurança

## Como reportar uma vulnerabilidade

Reporte de forma privada para a equipe responsável pelo sistema (não abra issue pública).
Inclua passos de reprodução, impacto e, se possível, um proof-of-concept.

Comprometemo-nos a acusar o recebimento em até 3 dias úteis e a tratar conforme a severidade.

## Controles implementados

- Autenticação JWT com refresh token rotativo e revogável; detecção de reuso.
- MFA (TOTP) para perfis com alçada.
- Bloqueio de conta contra brute force e rate limiting por IP.
- Política de senha forte (12+ com maiúscula, minúscula, número e símbolo).
- RBAC + alçada por valor (ABAC).
- Headers de segurança (HSTS, CSP, X-Frame-Options, nosniff) e remoção do header Server.
- Tratamento de erro sem vazamento de stack trace, SQL ou caminho de arquivo.
- CORS restrito por origem; documentação desativada em produção.
- Kardex append-only com hash encadeado; trilha de auditoria.
- Idempotência em operações sensíveis.

## Verificação contínua

- SAST (bandit) e auditoria de dependências (pip-audit) no CI.
- Suíte automatizada com testes contra ataque (bypass de autorização, brute force, injeção, replay).
- Dependabot para atualização de dependências (pip, docker, actions, npm).

## Gestão de segredos

Nunca comitar segredos. Em produção, `SECRET_KEY` e credenciais vêm de gerenciador de segredos
(Vault / AWS Secrets Manager) ou variáveis de ambiente, nunca de arquivo versionado.
