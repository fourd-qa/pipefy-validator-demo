# Plano de Dashboard de Produtividade Pipefy

Documento de referência da feature de Dashboard executivo com métricas de produtividade.
Última atualização: 2026-05-05.

---

## 1. Objetivo

Transformar o output existente do Pipefy Validator (snapshots JSON + diff classificado) em métricas de produtividade e qualidade que liderança consome em até 30 segundos por dia. Sair do "achei que a sprint foi boa" pro "time entregou 142 pontos com débito em 23%".

## 2. Escopo

### Métricas implementadas em fases

| Métrica | Sprint | Inspirada em |
|---|---|---|
| Snapshot Velocity | 1 | GitClear / Pluralsight Effective LOC |
| Pipe Debt Ratio | 1 | SonarQube Technical Debt |
| HMG → PRD Lead Time | 3 | DORA Lead Time |
| Phase Hot Spots | 3 | CodeScene Hot Spots |
| Burnup vs Blueprint | 4 | Jira Velocity / Burnup chart |
| Daily Activity Heatmap | 4 (extra) | GitHub Contributor Activity |

### Fora do escopo (limites honestos)

- **Autoria por desenvolvedor**: API GraphQL do Pipefy não expõe audit log de quem alterou estrutura. Não há solução técnica viável hoje.
- **Mutation testing**: Pipefy não permite executar mutações controladas em produção.
- **Coverage de testes unitários**: não existe conceito de teste unitário em automation Pipefy.

## 3. Sistema de pontuação (complexidade)

### Princípios

1. Lógica > estrutura > apresentação
2. Conexão > isolamento
3. Criar = modificar profundo > deletar > modificar superficial
4. Fan-out multiplica
5. Churn penaliza

### Pesos base por operação

Detalhados em `config/complexity_weights.json`. Resumo:

| Categoria | Faixa de pesos | Exemplos |
|---|---|---|
| Apresentação | 1-2 | Renomear label, mudar cor, editar description |
| Estrutura simples | 3-5 | Field texto, dropdown, mudar required |
| Estrutura conectada | 5-10 | Connection field, phase nova, deletar phase |
| Lógica | 6-15 | Automation move/update/HTTP, conditions |
| Integração | 8-15 | iPaaS flow, steps externos |

### Multiplicadores de fan-out

| Condição | Multiplicador |
|---|---|
| Field referenciado por 0 automations | x1.0 |
| Field referenciado por 1-3 | x1.5 |
| Field referenciado por 4+ | x2.0 |
| Field é triggerFieldId | x2.0 |
| Field aparece em condition | x2.5 |
| Phase é destino de move_card | x2.0 |

Em caso de múltiplas regras, usa-se o **maior multiplicador**, não soma.

### Multiplicadores de risco

| Condição | Multiplicador |
|---|---|
| Field novo sem description | x0.8 (penaliza déficit de doc) |
| Mudança em PRD sem espelho HMG | x1.5 (hotfix sem teste) |
| Mudança que diverge cross-env | x1.2 (promoção parcial) |
| Phase deletada com 100+ cards | x1.5 (risco de dado) |

### Penalidades de churn

| Condição | Desconto |
|---|---|
| Field criado e deletado em <7d | -3 |
| Automation criada e desativada em <7d | -8 |
| Phase criada e deletada em <30d | -10 |
| Mesmo field renomeado 3+ vezes em <14d | -2 |

### Categorias agregadoras (4 baldes pra UI)

- **Visual**: pesos 1-2
- **Estrutura**: pesos 3-8
- **Lógica**: pesos 6-15
- **Integração**: pesos 8-15

## 4. Arquitetura

### Princípio: tudo aditivo, zero risco no que existe

| Adição | Risco | Estratégia |
|---|---|---|
| `config/complexity_weights.json` | Zero | Arquivo novo |
| Engine de scoring (função pura) | Zero | Lê `validations.json` existente |
| Endpoints `/api/dashboard/*` | Zero | Prefixo isolado |
| Output `results/dashboard/*.json` | Zero | Arquivo separado, não toca `validations.json` |
| Frontend dashboard | Zero | Tela própria `/v2/dashboard` |
| Cron externo (Sprint 2) | Baixo | GitHub Actions, endpoint dedicado |
| Token persistente (Sprint 2) | Médio | Env var no Render, decisão de produto pra cliente real |

### Feature flags

`config/dashboard_features.json` controla quais cards ficam visíveis:

```json
{
  "velocity_enabled": true,
  "debt_enabled": false,
  "hotspots_enabled": false,
  "leadtime_enabled": false,
  "burnup_enabled": false,
  "shadow_mode": true
}
```

`shadow_mode: true` exibe banner "Métrica em validação" durante calibragem inicial.

## 5. Roteiro de implementação

### Sprint 1 (atual): Velocity + Debt manual
- [x] PLANO-DASHBOARD-PRODUTIVIDADE.md
- [x] `config/complexity_weights.json` com pesos default
- [ ] Engine de scoring no `server.py` (função pura)
- [ ] Endpoint `GET /api/dashboard/velocity`
- [ ] UI: card de Velocity no dashboard com KPI + sparkline
- [ ] Engine de débito (regras estáticas)
- [ ] Endpoint `GET /api/dashboard/debt`
- [ ] UI: card de Debt Ratio com gauge + donut
- [ ] Pytest dedicado (~15 casos)

### Sprint 2: Automação
- [ ] UI seleção de pipes monitorados (`config/monitored_pipes.json`)
- [ ] Endpoint `POST /api/cron/snapshot` com `X-Cron-Token`
- [ ] GitHub Actions cron `*/30 * * * *`
- [ ] Env var `MONITOR_PIPEFY_TOKEN` no Render
- [ ] Storage filesystem (`snapshots/auto/<pipe>/<timestamp>.json`)

### Sprint 3: Hot Spots + Lead Time
- [ ] Engine de hot spots (frequência x complexidade por phase)
- [ ] Engine de lead time HMG→PRD (timestamps de snapshots)
- [ ] UI: heatmap + line chart
- [ ] Pré-requisito: 1-2 semanas de histórico

### Sprint 4: Burnup + Email
- [ ] UI marcar snapshot como blueprint
- [ ] Engine de cobertura atual vs blueprint
- [ ] Resend API + template HTML
- [ ] Cron diário `0 18 * * 1-5`

## 6. KPIs do projeto (meta-métricas)

| Métrica | Como medir | Meta |
|---|---|---|
| Tempo do líder no dashboard por dia | analytics frontend simples | < 10 min |
| % de líderes que abrem o email diário | tracking de open rate | > 70% |
| Decisões em retrospectiva citando dado do dashboard | survey trimestral | crescendo |
| Bugs detectados via Hot Spot antes de chegarem em PRD | manual log | qualquer número > 0 já é vitória |

## 7. Decisões em aberto

- **Privacidade do token persistente** (Sprint 2): pro `pipefy/` original com cliente real, precisa decisão contratual.
- **Storage histórico** (Sprint 2-3): começar em filesystem efêmero ou já investir em S3?
- **Provider de email** (Sprint 4): Resend é simples mas é mais um vendor; SES da AWS é mais corporate; Gmail SMTP é mais frugal.
- **Calibragem dos pesos**: 2 sprints em shadow mode antes de ser usado pra avaliação real.

## 8. Risco e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Pesos virarem polêmica política no time | Média | Shadow mode 2 sprints + tudo em PR no git |
| Cron disputar `_state["running"]` com run manual | Baixa | Lock separado + skip se conflito |
| Token vazar via cron | Baixa | Env var no Render, nunca passa pelo navegador |
| Render free dorme e perde snapshots | Alta | Documentado, decisão consciente, upgrade pra S3 quando necessário |
| Líder não usar a ferramenta | Média | Email diário força o ponto de contato; survey após 1 mês |
