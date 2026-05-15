# Handoff — Security Scan (Fase A do L4)

Documento canônico da Frente 1 do `PLANO-VALIDACAO-HMG-PRD.md`: equivalente Gitleaks + Snyk Code aplicado a automations Pipefy.

Última atualização: 2026-05-15.

---

## TL;DR

- **O que é**: scanner de regras semânticas sobre URLs, headers e body de automation HTTP. Procura credenciais hardcoded, URLs HTTP sem TLS, IPs internos, indicadores de ambiente de teste em PRD.
- **Onde está**: `/v2/security-scan` (UI), `POST /api/security-scan` (engine), `config/semantic_rules.json` (regras).
- **Login**: restrito a `lideranca`.
- **Testes**: 33 pytest verdes (`tests/python/test_semantic_scanner.py`).
- **Estado**: standalone — não integrado ao fluxo do validador Robot. Usuário cola JSON das automations (ou consome via API direto) e roda scan.

---

## 1. Arquitetura

```
semantic_scanner.py       Engine pura: load_rules, scan_targets, extract_targets,
                          summarize_findings. Sem efeito colateral.
config/semantic_rules.json  9 regras default com pattern + fields + severity +
                          env_restrict + enabled. Editável via PR.
server.py                 POST /api/security-scan, GET /api/security-scan/rules,
                          GET /v2/security-scan (HTML).
web/designs/tela_security_scan.html  UI: textarea pra JSON + env_label + botão
                          scan + lista de findings agrupada por severidade.
tests/python/test_semantic_scanner.py  33 casos: load_rules, cada regra default
                          em TP/TN, env_restrict, extract de GraphQL, summary,
                          endpoint gating, gating HTML.
```

## 2. Regras default

9 regras em `config/semantic_rules.json`:

| ID | Categoria | Severidade | Env | O que detecta |
|---|---|---|---|---|
| `url_no_tls_in_prd` | url_security | high | PRD | URL `http://` (sem TLS) |
| `url_internal_ip` | url_security | high | qualquer | localhost, 127.*, 192.168.*, 10.*, 172.16-31.* |
| `url_with_test_subdomain_in_prd` | env_mismatch | high | PRD | Subdomínio `hmg.`, `staging.`, `qa.`, `test.`, `sandbox.`, `dev.` |
| `token_in_query_string` | secret_leak | high | qualquer | `?token=...`, `?api_key=...`, `?secret=...` na URL |
| `bearer_token_in_headers` | secret_leak | high | qualquer | `Bearer <20+ chars>` ou `Basic <20+ chars>` em headers |
| `credential_in_body` | secret_leak | high | qualquer | `"api_key":"..."`, `"password":"..."`, `"secret_key":"..."` no body |
| `email_de_teste_in_prd` | env_mismatch | med | PRD | `qa@`, `test@`, `+test@`, `@example.com`, `@mailinator.com` |
| `aws_access_key` | secret_leak | high | qualquer | `AKIA[0-9A-Z]{16}` |
| `github_token` | secret_leak | high | qualquer | `gh[pousr]_<36+>` |

**`env_restrict`**: regra só dispara quando `target.env_label` bate. Permite catalogar "isso é OK em HMG mas problema em PRD".

**Snippets** dos findings têm máscara automática: tokens com 8+ chars viram `abcd***` no output, evitando relog de credenciais em logs.

## 3. Endpoints

### `POST /api/security-scan`
Gated `lideranca`. Body:

```json
{
  "automations": [
    {"id": "auto_1", "name": "X", "action_params": {"url": "http://...", "headers": "...", "body": "..."}}
  ],
  "env_label": "PRD"
}
```

Aceita também `{"targets": [...]}` com formato pré-extraído.

Retorna:
```json
{
  "ok": true,
  "findings": [{"rule_id", "category", "severity", "message", "target_kind",
                "target_name", "target_id", "field", "snippet", "env_label"}],
  "summary": {"total", "by_severity": {high, med, low},
              "by_category": {...}, "by_rule": {...}},
  "rules_count": 9,
  "targets_count": 1
}
```

### `GET /api/security-scan/rules`
Gated `lideranca`. Lista regras configuradas sem expor o regex (info sensível). Útil pra UI mostrar quais regras estão ativas.

## 4. UI

`/v2/security-scan`:
- Hero vermelho indicando contexto de segurança
- Textarea pra JSON (aceita array de automations ou `{targets, env_label}`)
- Selector de `env_label` (PRD/HMG/nenhum)
- Sidebar com lista de regras ativas (carrega via `/api/security-scan/rules`)
- Botão "Carregar exemplo" pré-popula JSON com 1 automation suja + 1 limpa pra demonstração
- Findings agrupados por severidade (high → med → low), com sev pill colorida, rule_id mono, mensagem, meta info, snippet mascarado

## 5. Como usar

### Fluxo manual (atual)
1. Líder roda `automations_list.graphql` no Pipefy GraphiQL ou Postman pra um pipe PRD
2. Copia o array `data.automations.edges[*].node` (ou ajusta pra `[{id, name, action_params}]`)
3. Cola em `/v2/security-scan`, escolhe `env_label=PRD`, clica "Rodar scan"
4. Lê findings, abre PR pra corrigir cada um

### Fluxo programático
```bash
curl -u lideranca:lideranca -X POST \
  -H "Content-Type: application/json" \
  -d @automations.json \
  https://pipefy-validator-demo.onrender.com/api/security-scan
```

## 6. Pendências e próximos passos

### Pendência 1: auto-coleta de automations
O cron de snapshots (`_fetch_and_save_pipe_snapshot`) só coleta `pipe { phases, start_form_fields, labels }` — sem automations. Pra automatizar o scan, precisaria estender a query GraphQL pra trazer `automations { id, name, action_params }`. Custo: 1 alteração na query + ajuste no schema do snapshot. Risco: aumenta tamanho dos snapshots, pode bater rate limit do Pipefy.

### Pendência 2: alertas no email diário
Quando a Pendência 1 estiver resolvida, faz sentido o email diário rodar o scan automaticamente sobre o último snapshot de cada pipe PRD e injetar findings high como alertas. Em `daily_digest.build_daily_digest` adicionaria um bloco `security_scan` no payload.

### Pendência 3: histórico de scans
Hoje cada scan é stateless. Pra evoluir pra L5 (drift de segurança), os findings precisariam ser persistidos com timestamp pra mostrar evolução. Diretório candidato: `results/security_scans/<pipe>/<timestamp>.json`.

### Próximos níveis do PLANO-VALIDACAO-HMG-PRD
- **Frente 2 (Fase B): SonarQube equivalent** — quality scanner: field criado e não usado, automation com condition que nunca pode ser true, naming convention. Reusa o pattern desta Frente 1.
- **Frente 3 (Fase C): Datadog Synthetics equivalent** — smoke pós promoção: card teste, move pelas phases críticas, valida webhooks receberam payload correto.

## 7. Riscos e mitigações

| Risco | Status | Mitigação |
|---|---|---|
| False positive em regex de secret | Provável | Severity como sinal, não bloqueio. Líder revisa. enabled=false pra silenciar regra ruim. |
| Regex inválido derruba scan | Mitigado | `load_rules` ignora regras com regex inválido, não quebra o resto. |
| Snippet vaza segredo em log | Mitigado | Máscara automática (`abcd***`) quando match > 8 chars. |
| UI aceita JSON malicioso | Baixo | HTML escape no render dos findings. JSON.parse em vez de eval. |
| Endpoint expõe regex sensível | Mitigado | `/api/security-scan/rules` omite o campo `pattern`. |
