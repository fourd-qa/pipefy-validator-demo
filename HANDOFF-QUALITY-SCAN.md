# Handoff — Quality Scan (Fase B do L4)

Documento canônico da Frente 2 do `PLANO-VALIDACAO-HMG-PRD.md`: equivalente SonarQube aplicado a pipes Pipefy.

Última atualização: 2026-05-15.

---

## TL;DR

- **O que é**: scanner estático sobre snapshot do pipe que procura dead fields, triggerFieldIds órfãos, automations com complexidade alta, IDs hardcoded em conditions, automations inativas com triggers esquecidos, naming fora de padrão.
- **Onde está**: card "Quality" em `/v2/dashboard` (live, col-6), endpoints `/api/dashboard/quality`, `/api/quality-scan/auto`, `/api/quality-scan/history`, `/api/quality-scan/rules`. Regras em `config/quality_rules.json`. Histórico em `results/quality_scans/<pipe>/<ts>.json`.
- **Login**: restrito a `lideranca`.
- **Testes**: 30 pytest verdes (`tests/python/test_quality_scanner.py` + integração no cron).
- **Estado**: integrado ao cron — toda execução do `/api/cron/snapshot` salva run no histórico. Dashboard tem card live + trend disponível via endpoint.

---

## 1. Arquitetura

```
quality_scanner.py           Engine puro: load_rules, scan_pipe_quality,
                             summarize_findings, persist_scan_run,
                             list_scan_runs, compute_quality_trend.
config/quality_rules.json    7 checks default (6 habilitados, 1 disabled
                             por ser opt-in: naming convention).
server.py                    _run_and_persist_quality_scan chamado no fim
                             de _fetch_and_save_pipe_snapshot. 4 endpoints
                             novos. /api/dashboard/data inclui quality.
web/designs/tela_dashboard.html  Card "Quality" col-6 ao lado do Security.
                             Mesmo padrão visual (CSS namespace .qual-*).
results/quality_scans/<pipe>/<ts>.json  Histórico persistido (retenção 50).
tests/python/test_quality_scanner.py  30 casos cobrindo cada check em TP/TN,
                             engine, endpoints, histórico, integração com
                             cron e /api/dashboard/data.
```

## 2. Checks default

7 checks em `config/quality_rules.json`:

| ID | Categoria | Severidade | Enabled | Detecta |
|---|---|---|---|---|
| `dangling_trigger_field` | consistency | high | ✓ | `triggerFieldId` aponta pra field que não existe no schema |
| `high_complexity_automation` | complexity | med | ✓ | Automation com ≥ N expressions (threshold=8 default) |
| `dead_start_form_field` | dead_code | med | ✓ | Field do start form sem nenhuma automation referenciando |
| `dead_phase_field` | dead_code | low | ✓ | Field de phase sem referência (requer snapshot v1.2+) |
| `inactive_automation_with_trigger` | stale | med | ✓ | `active=false` mas tem `triggerFieldIds` configurados |
| `magic_id_in_condition` | magic_value | low | ✓ | `condition.value` parece UUID ou número longo (min_length=12) |
| `naming_inconsistent_field` | naming | low | ✗ | Label de field fora de regex configurável. Off por default (cada cliente tem padrão diferente) |

**Como referenciamos fields**: `triggerFieldIds` em `event_params` + `field_address` em `condition.expressions`. Se algum check precisar olhar `action_params.body` no futuro, basta estender `_referenced_field_ids`.

**Pra ativar naming check**: editar `quality_rules.json`, setar `enabled: true` e ajustar `label_regex` pro padrão da empresa (ex: `"^[A-Z][a-zA-Z ]+$"` exige PascalCase com espaços).

## 3. Snapshot v1.2

Pra rodar `dead_phase_field`, a query GraphQL do cron foi estendida pra incluir `phases { fields { id label type required } }`. Snapshot ganhou bump pra `tool_version: "1.2"`.

Backwards compat:
- v1.0 (Sprint 2): sem `automations` nem phase fields → scanner skipta checks que precisam desses dados
- v1.1 (Fase A pendência 1): com `automations`, sem phase fields → roda tudo menos `dead_phase_field`
- v1.2 (Fase B): completo

O card no dashboard mostra um warning quando o snapshot é < v1.2.

## 4. Endpoints

### `GET /api/dashboard/quality?pipe_id=...`
Default = primeiro pipe enabled em `monitored_pipes`. Retorna shape pronto pro card: `{available, total, by_severity, by_category, top_checks, top_findings_high, rules_count, snapshot_version, snapshot_timestamp}`.

### `GET /api/quality-scan/auto?pipe_id=...`
Mesma engine. Útil pra UI/CLI scannear sob demanda. Sem `pipe_id` retorna 400.

### `GET /api/quality-scan/history?pipe_id=...&limit=10`
Trend computado de `results/quality_scans/`:
- `series` (timestamp + total + by_severity por run)
- `delta_last_vs_prev` (variação entre as 2 últimas runs)
- `new_findings` (apareceram só na última, por `(check_id, target_id)`)
- `resolved_findings` (estavam na anterior, sumiram)
- `latest_summary`

### `GET /api/quality-scan/rules`
Lista checks configurados (sem regex compilado).

## 5. UI

Card "🧹 Quality Scan" em `/v2/dashboard` (`col-6`, ao lado do Security):
- KPI total com cor por severidade dominante
- 3 sub-KPIs (high/med/low)
- Top 5 checks mais disparados
- Top 5 findings high com `check_id`, `target_name`, `detail`
- Mostra warning quando snapshot < v1.2 ("sem phase fields")
- Picker de pipe próprio

## 6. Pendências e próximos passos

### Pendência 1: card de trend
Endpoint `/api/quality-scan/history` já existe e calcula delta + new/resolved. UI ainda não consome — apenas o card live é mostrado. Próximo polish: graph line ou KPI delta no card.

### Pendência 2: UI standalone
Não tem `/v2/quality-scan` ainda (igual o `/v2/security-scan` da Fase A). Card no dashboard cobre o caso comum, mas pra investigar profundo seria útil ter uma tela dedicada com lista expansível por finding + filtros.

### Próximos níveis do plano L4
- **Frente 3 (Fase C)**: Datadog Synthetics equivalent — smoke pós promoção: cria card teste, move pelas phases críticas, valida webhooks
- **Fase D**: SLAs por fase, permissões, integrações, email templates
- **Fase E**: drift detection contínuo

## 7. Riscos e mitigações

| Risco | Status | Mitigação |
|---|---|---|
| False positive em dead field | Possível | Severity como sinal. `dead_phase_field` é low por isso. Cliente pode acionar `enabled: false` por check |
| Snapshot v1.0/v1.1 antigo | Mitigado | Engine não quebra com schema parcial; UI mostra warning |
| Check com bug derruba scan inteiro | Mitigado | `scan_pipe_quality` faz `try/except` por check |
| naming_regex inválido | Mitigado | `load_rules` ignora regra; outras seguem |
| Inflação do histórico | Mitigado | Retenção mantém últimas 50 runs por pipe |
