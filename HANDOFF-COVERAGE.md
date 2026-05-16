# Handoff — Coverage + Blast Radius (Fase D parte 1 do L4)

Documento canônico da Fase D (parcial) do `PLANO-VALIDACAO-HMG-PRD.md`: blast radius + cobertura básica. SLA detalhado, permissões, email templates e integrações ficam pra Fase D parte 2.

Última atualização: 2026-05-15.

---

## TL;DR

- **O que é**: scanner que cruza dados do snapshot pra mostrar:
  - **Blast Radius**: pra cada phase, quantos cards reais estão lá + quantas automations entram/saem. Custo de mudar.
  - **Coverage findings**: phases órfãs (sem automation entrando), phases sem SLA, phases sem description, fields sem description, phases "heavy" (>= 50 cards).
- **Onde está**: card "Coverage + Blast Radius" em `/v2/dashboard`, endpoints `/api/dashboard/coverage`, `/api/coverage/auto`, `/api/coverage/history`. Engine em `coverage_scanner.py`. Config em `config/coverage_rules.json`. Histórico em `results/coverage_scans/<pipe>/<ts>.json`.
- **Login**: restrito a `lideranca`.
- **Testes**: 23 pytest verdes (`tests/python/test_coverage_scanner.py`) + 1 teste de integração no cron.
- **Estado**: integrado ao cron — toda execução salva run no histórico. Dashboard tem card live.

---

## 1. Arquitetura

```
coverage_scanner.py          Engine pura: load_rules (com defaults seguros),
                             compute_blast_radius, compute_phase_coverage,
                             compute_field_coverage, scan_pipe_coverage,
                             summarize_coverage, persist + list.
config/coverage_rules.json   4 thresholds/flags (heavy_phase_threshold=50,
                             require_description_for_fields=true,
                             require_sla_for_phases=true,
                             flag_orphan_phases=true).
server.py                    _run_and_persist_coverage_scan no fim de
                             _fetch_and_save_pipe_snapshot. 3 endpoints.
                             /api/dashboard/data inclui coverage.
web/designs/tela_dashboard.html  Card "Coverage + Blast Radius" col-12 antes
                             do Smoke. Mostra cards totais, findings count,
                             top 5 phases por blast radius, findings high.
                             Warning quando snapshot < v1.3.
results/coverage_scans/<pipe>/<ts>.json  Histórico (retenção 50).
```

## 2. Snapshot v1.3

Pra computar blast radius, query GraphQL do cron foi estendida pra incluir nos `phases`:
- `description`
- `expiration_time_by_card` (SLA)
- `cards_count`

Em `fields` (start_form e phase fields): `description`.

**Bump pra `tool_version: "1.3"`**. Backwards compat:
- v1.0: sem automations nem phase fields → coverage só consegue checar phases existem (cards_count=None, automations vazio)
- v1.1: com automations → consegue detectar orphan phases
- v1.2: com phase fields → field coverage funciona
- v1.3: completo (cards_count + SLA + description)

Card no dashboard mostra warning quando snapshot é < v1.3 ("coverage parcial").

## 3. Findings (checks)

| ID | Categoria | Severidade | Quando dispara |
|---|---|---|---|
| `heavy_phase` | blast_radius | high | `cards_count >= heavy_phase_threshold` (default 50) |
| `orphan_phase` | consistency | med | Phase sem nenhuma automation `action_params.to_phase_id` apontando |
| `phase_without_sla` | sla | low | `expiration_time_by_card` falsy |
| `phase_without_description` | documentation | low | `description` falsy |
| `field_without_description` | documentation | low | `description` falsy (start_form ou phase fields) |

## 4. Blast Radius

Pra cada phase do snapshot, retorna:
```json
{
  "phase_id": "ph_xyz",
  "phase_name": "Análise de Crédito",
  "cards_count": 42,
  "automations_in": 3,
  "automations_out": 5,
  "automations_total": 8,
  "weight": 82
}
```

`weight = cards_count + automations_total * 5`. Lista ordenada por weight desc.

Uso: antes de propor mudança numa phase, líder olha quanto blast radius. Phase com 100 cards + 5 automations é arriscado mudar.

## 5. Endpoints

| Endpoint | Auth | O que faz |
|---|---|---|
| `GET /api/dashboard/coverage?pipe_id=...` | lideranca | Shape do card live. Default = primeiro pipe enabled |
| `GET /api/coverage/auto?pipe_id=...` | lideranca | Idem, ad-hoc |
| `GET /api/coverage/history?pipe_id=...&limit=10` | lideranca | Lista runs persistidas |

`/api/dashboard/data` agora inclui bloco `coverage` agregado.

## 6. Pendências e próximos passos

### Pendência 1: Fase D parte 2 — SLA detalhado, permissões, email templates, integrações
Frente original do plano inclui:
- **SLAs**: hoje só vê se está configurado (sim/não). Pra ver violações reais (cards passaram do prazo), precisa query `cards { expiration_time, finished_at }` com filtro de prazo vencido.
- **Permissões**: `pipe { members { role } } + start_form { public }`. Precisa de query GraphQL nova.
- **Email templates**: `automation { action_id="send_email" action_params.template }`. Já chega no snapshot v1.3 (`action_params` é JSON aberto), só falta engine de comparação cross-env de templates.
- **Integrações**: detectar drift em conexões com Database Pipefy, Drive, Slack. Query nova.

Cada uma é uma frente própria. Recomendo fazer em ordem de valor: permissões primeiro (segurança), depois SLAs (operacional), depois email/integrações.

### Pendência 2: trend de coverage
`compute_security_trend` e `compute_quality_trend` existem; `coverage_scanner` ainda não tem `compute_coverage_trend`. Padrão é o mesmo, só faltou implementar.

### Pendência 3: cross-env (HMG vs PRD blast radius)
Hoje coverage olha 1 pipe. Pra "phase X em PRD tem 100 cards mas mesma phase em HMG só tem 2" precisaria comparar pares. Engine existente `compute_leadtime` já pareia HMG/PRD pelo nome base — pode reusar essa lógica.

### Pendência 4: alertas no email diário
Heavy phases (severity high) deveriam virar alertas no `daily_digest.build_daily_digest`. Padrão é igual ao security_high.

## 7. Riscos e mitigações

| Risco | Status | Mitigação |
|---|---|---|
| `cards_count` não existe no schema Pipefy real | Possível | Engine trata `null` como N/A. Backwards compat com v1.0-1.2 que não têm o campo |
| Threshold de heavy_phase é arbitrário (50) | Aceito | Configurável em `config/coverage_rules.json`. Ajuste por cliente |
| Orphan detection false-positive em phase de entrada | Possível | Phase inicial sempre vai parecer "orphan" (não tem automation MOVENDO pra ela). Aceito por ora — líder julga |
| Inflação do histórico | Mitigado | Retenção 50 igual aos outros scanners |
