# Handoff — Dashboard de Produtividade

Documento pra retomar o trabalho num chat novo sem perder contexto.
Última atualização: 2026-05-05, fim de sessão. Sprints 1 e 2 entregues.

---

## TL;DR

- **Onde estamos**: Sprints 1 e 2 do `PLANO-DASHBOARD-PRODUTIVIDADE.md` no ar. Sprint 3 e Sprint 4 pendentes.
- **Repositório**: `fourd-qa/pipefy-validator-demo` (público), branch `main`.
- **Deploy**: Render free tier. URL `https://pipefy-validator-demo.onrender.com`.
- **Testes**: 208 pytest + 49 vitest verde no commit `728d3a2`.
- **Login**: `lideranca / lideranca` vê o dashboard. `demo / <APP_PASSWORD>` continua usando o validador normal sem ver o dashboard.

---

## 1. O que está no ar hoje

### 1.1 Login `lideranca` (commit `315555a`)

- `LIDERANCA_USERNAME` / `LIDERANCA_PASSWORD` (defaults `lideranca` / `lideranca`).
- `/api/whoami` retorna `{role: 'lideranca'|'demo'|'open'}`.
- Pill verde "Dashboard" no header só aparece pra `lideranca` (e modo dev sem `APP_PASSWORD`).
- 15 pytest dedicados em `tests/python/test_dashboard.py`.

### 1.2 Sprint 1 — Velocity + Debt Index (commits `bb61497` e `728d3a2`)

**Engine**: `dashboard_metrics.py` (módulo Python puro, sem efeito colateral)
- `extract_prefix(divergencia)`: extrai `[CATEGORIA]` da string.
- `score_divergencia(text, weights)`: pontua 1 divergência.
- `score_validations(validations, weights)`: agrega scoring inteiro.
- `classify_debt_level(pts)`: CLEAN (0) / LOW (1-30) / MEDIUM (31-80) / HIGH (80+).
- `compute_velocity(validations_path, weights_path)`: KPI da run mais recente.
- `compute_debt(validations_path, weights_path)`: Debt Index categórico.

**Pesos**: `config/complexity_weights.json` (24 prefixos mapeados, 4 baldes: visual / structure / logic / integration). Editável via PR.

**Endpoints**:
- `GET /api/dashboard/data` (gated lideranca): velocity + debt agregados.
- `GET /api/dashboard/velocity` (gated): só velocity.
- `GET /api/dashboard/debt` (gated): só debt.

**UI** (`web/designs/tela_dashboard.html`):
- Banner "Métricas em validação" (shadow mode declarado no plano).
- Card Velocity: KPI grande de pontos + breakdown por balde com barras + top 6 divergências por peso.
- Card Run Meta: status, pipes origem/destino, total divergências, timestamp.
- Card Debt Index: gauge categórico colorido + composição por área + top 8 issues.
- Stubs visuais dos próximos cards (Lead Time, Hot Spots, Burnup) com tag de sprint.

**Testes**: `tests/python/test_dashboard_metrics.py` (38 casos).

### 1.3 Sprint 2 — Cron + Pipes Monitorados (commit `728d3a2`)

**Endpoints novos**:
- `GET /api/dashboard/monitored-pipes` (gated): lista pipes + flags de configuração.
- `POST /api/dashboard/monitored-pipes` (gated): salva lista. Body: `{pipes: [{id, name, repo_id, env_label, enabled}]}`.
- `POST /api/cron/snapshot` (sem Basic Auth, header `X-Cron-Token`): coleta snapshots dos pipes monitorados via Pipefy GraphQL e salva em `snapshots/auto/<pipe_id>/<timestamp>.json`.
- `GET /api/dashboard/auto-snapshots/<pipe_id>` (gated): lista snapshots históricos coletados.

**Env vars novas** (todas opt-in, default vazio = feature desligada):
- `CRON_SNAPSHOT_TOKEN`: secret compartilhado entre Render e GitHub Actions.
- `MONITOR_PIPEFY_TOKEN`: Bearer do Pipefy usado pelo cron (sem `Bearer` no início, só o token).
- `MONITOR_PIPEFY_BASE_URL`: default `https://api.pipefy.com/graphql`.
- `MONITOR_PIPEFY_ORG_ID`: opcional, pra futuras queries que filtram por org.

**Cron externo**: `.github/workflows/cron-snapshot.yml`
- Schedule `*/30 11-22 * * 1-5` (a cada 30min, 8-19h BRT, dias úteis).
- Manual via GitHub Actions UI: `workflow_dispatch`.
- Secrets necessários no GitHub: `APP_URL` (URL do Render) + `CRON_TOKEN` (mesmo valor que `CRON_SNAPSHOT_TOKEN` no Render).

**UI**: card "Pipes monitorados" no dashboard com tabela editável (nome / UUID / repo_id / env_label / toggle ativo), botões "+ Adicionar pipe" e "Salvar configuração", e 3 pills de status mostrando: pipes ativos, cron token configurado, monitor token configurado.

**Testes**: `tests/python/test_dashboard_cron.py` (19 casos).

---

## 2. Pendências críticas pra ativar Sprint 2 em produção

A Sprint 2 está toda no ar, mas o cron NÃO vai disparar até você fazer 3 setups manuais. Sem isso, o card "Pipes monitorados" mostra os pills vermelhos e o cron retorna 503.

### Setup 1: Env vars no Render

Painel do Render → seu serviço → Environment → Add:

| Nome | Valor |
|---|---|
| `CRON_SNAPSHOT_TOKEN` | gere um string aleatório longo, ex: `openssl rand -hex 32` |
| `MONITOR_PIPEFY_TOKEN` | seu PAT do Pipefy (sem prefixo "Bearer") |
| `MONITOR_PIPEFY_BASE_URL` | `https://api.pipefy.com/graphql` (default ok) |

Render vai redeployar automaticamente após salvar.

### Setup 2: Secrets no GitHub

Repo `fourd-qa/pipefy-validator-demo` → Settings → Secrets and variables → Actions → New repository secret:

| Nome | Valor |
|---|---|
| `APP_URL` | `https://pipefy-validator-demo.onrender.com` |
| `CRON_TOKEN` | mesmo valor que você botou em `CRON_SNAPSHOT_TOKEN` no Render |

### Setup 3: Adicionar pipes no dashboard

1. Abre `https://pipefy-validator-demo.onrender.com/v2/dashboard` como `lideranca`.
2. Card "Pipes monitorados" → "+ Adicionar pipe".
3. Preenche linha: nome, UUID Pipefy (formato `1234abcd-...`), repo_id (numérico), ambiente (HMG/PRD).
4. Marca toggle ativo.
5. Clica "Salvar configuração".

### Validação: dispara cron manual

GitHub repo → Actions → "Cron Snapshot" → Run workflow.
Espera ~30s, abre o run, vê o body retornado pelo endpoint. Se `ok: true` e `total_pipes` correto, está rodando.
Após primeira execução, os snapshots aparecem em `snapshots/auto/<pipe_id>/` no container do Render (efêmero).

---

## 3. Limitações conhecidas do que está no ar

### 3.1 Render free tier dorme após 15min ocioso
Cron `*/30 11-22 * * 1-5` mantém vivo durante horário comercial. Fora disso, container hiberna e snapshots em filesystem somem ao redeploy. Decisão consciente, documentada. Sprint 3+ pode evoluir pra storage em S3.

### 3.2 Lista de pipes salva em `config/`
`config/monitored_pipes.json` é volume mount no container do Render. **Quando o container hiberna e redeploya, a lista some.** Pra contornar: ou commitar o arquivo no repo (o que faz a config virar pública, ruim pra cliente real) ou subir pra disco persistente do Render (paid).

Pro demo público com sandbox FourD, **commitar no repo é aceitável**. Mas hoje commitamos só o template vazio, então o usuário precisa repreencher após cada hibernação. Pendência: decidir se UI deve copiar lista pro localStorage do `lideranca` como backup, ou se gera GitHub commit automaticamente.

### 3.3 Validations.json é rolling
A app sobrescreve `results/validations.json` a cada run. Isso significa que o card Velocity sempre mostra a última run, sem histórico. Pra histórico real (Sprint 3), precisamos:
- Ou snapshots auto rodando (Sprint 2 em ação) e parsing deles
- Ou reescrever o `/api/run` pra arquivar runs em `results/history/<timestamp>.json`

### 3.4 Concorrência cron vs run manual
Endpoint `/api/cron/snapshot` é independente de `_state["running"]`, então não dá conflito. Mas se cron e run manual chamarem GraphQL ao mesmo tempo, podem bater rate limit do Pipefy. Não tratamos isso. Probabilidade baixa, vale acompanhar logs nas primeiras semanas.

### 3.5 Pendência herdada: flake do teste de esterilização
Veja `memory/project_pendencia_flake_sterilize.md`. Não relacionada ao dashboard, mas anotada pra não esquecer.

---

## 4. Arquivos relevantes do projeto

```
pipefy-validator-demo/
├── PLANO-DASHBOARD-PRODUTIVIDADE.md    canônico da feature
├── HANDOFF-DASHBOARD.md                este arquivo
├── server.py                           +monitored-pipes, +cron, +dashboard endpoints
├── dashboard_metrics.py                engine pura (NOVO)
├── config/
│   ├── complexity_weights.json         24 prefixos + multiplicadores (NOVO)
│   └── monitored_pipes.json            lista de pipes do cron (NOVO)
├── web/designs/
│   ├── tela_dashboard.html             4 cards: Velocity, RunMeta, Debt, Monitored Pipes
│   └── assets/v2_utils.js              renderDashboardLink() já injetado em todas as 3 telas existentes
├── tests/python/
│   ├── test_dashboard.py               15 casos: whoami + gates + lideranca login
│   ├── test_dashboard_metrics.py       38 casos: scoring + endpoints velocity/debt
│   └── test_dashboard_cron.py          19 casos: monitored-pipes + cron + auto-snapshots
└── .github/workflows/
    └── cron-snapshot.yml               cron */30 chama /api/cron/snapshot
```

---

## 5. Próximos passos: Sprint 3

### Sprint 3 — Hot Spots + Lead Time

**Pré-requisito**: 1-2 semanas de snapshots históricos acumulados pelo cron (Sprint 2 rodando em produção).

**Hot Spots**
- Engine em `dashboard_metrics.py` que carrega N snapshots de `snapshots/auto/<pipe_id>/`, calcula:
  - Frequência de mudança por phase (quantas vezes phase X mudou em N snapshots)
  - Complexidade média por phase (peso médio das mudanças que envolveram a phase)
  - Score = frequência × complexidade
- Endpoint `GET /api/dashboard/hotspots`
- UI: heatmap 2D (linhas = phases, colunas = semanas) ou scatter plot (frequência × complexidade) ou ambos

**Lead Time HMG → PRD**
- Engine que casa snapshots de pipe HMG e PRD pelo `env_label` em `monitored_pipes.json`, calcula tempo entre elemento aparecer em HMG e mesmo elemento aparecer em PRD.
- Pré-requisito: pares HMG/PRD configurados na lista de monitored.
- Endpoint `GET /api/dashboard/leadtime`
- UI: histograma de distribuição + line chart de mediana semanal.

**Bibliotecas de gráfico**: Chart.js via CDN (~70KB) cobre line/bar/scatter/donut. ApexCharts (~190KB) só se precisar heatmap nativo (pode fazer em CSS Grid puro também).

**Estimativa**: 14-17h, 1 sprint corrida.

### Sprint 4 — Burnup vs Blueprint + Email

**Burnup**
- UI no dashboard pra marcar um snapshot como `is_blueprint: true` em `metadata.json` dele.
- Engine que compara snapshot atual vs blueprint marcado, calcula % de cobertura por categoria (phases / fields / automations).
- Endpoint `GET /api/dashboard/burnup`
- UI: line chart com 2 séries (real vs meta) + stacked area por categoria + progress bars por categoria.

**Email diário**
- Provider sugerido: **Resend** (free tier 100 emails/dia, API JSON simples).
- Env vars: `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO` (lista).
- Endpoint `POST /api/cron/daily-email` (mesmo padrão de auth do cron snapshot, com `X-Cron-Token`).
- GitHub Actions cron `0 18 * * 1-5` chama o endpoint.
- Template HTML enxuto: 3 KPI cards (Velocity, Debt, Lead Time) + alertas (hot spots novos, churn detectado).
- Testes mockando Resend API.

**Estimativa**: 15-18h, 1 sprint.

---

## 6. Sistema de pontuação (resumo)

Detalhes completos em `PLANO-DASHBOARD-PRODUTIVIDADE.md` seção 3.

**Princípios**: lógica > estrutura > apresentação. Conexão > isolamento. Criar > modificar profundo > deletar > rename. Fan-out multiplica. Churn penaliza.

**Pesos por categoria** (em `config/complexity_weights.json`):
- Apresentação (1-2): rename label, mudar cor, rename phase/field, description.
- Estrutura simples (3-5): field texto/email/data/dropdown, mudar required, mudar tipo (alto risco).
- Estrutura conectada (5-10): connection field, phase nova, deletar phase com cards, SLA.
- Lógica (6-15): automation move/update/HTTP, conditions (5/8/12/15 por complexidade).
- Integração (8-15): iPaaS flow, steps, mapping.

**Multiplicadores de fan-out**: x1.0 a x2.5 (campo referenciado por N automations, é triggerFieldId, aparece em condition).

**Multiplicadores de risco**: x0.8 (sem doc) a x1.5 (PRD sem HMG, phase com 100+ cards).

**Penalidades de churn**: -3 a -10 pontos (criar e deletar em janela curta).

**4 baldes de UI**: visual / structure / logic / integration.

---

## 7. Cenários de uso (resumo da história do Carlos)

1. **Manhã**: email com 3 KPIs (Velocity, Debt, Lead Time) + alertas. 30 segundos.
2. **Diário**: dashboard pra investigar sinal vermelho. ~10 min.
3. **Sexta**: retro com comparativo sprint vs sprint na TV.
4. **Mensal**: comitê com burnup vs blueprint pra responder "quando termina?".

Detalhes em conversa anterior do chat (resumida em `PLANO-DASHBOARD-PRODUTIVIDADE.md` seção 1 e seção 2).

---

## 8. Como retomar num chat novo

Cole no início do chat novo:

```
Lê o HANDOFF-DASHBOARD.md desta pasta. Estamos no fim da Sprint 2 do
Dashboard de Produtividade. Próximo passo: Sprint 3 (Hot Spots + Lead Time).
Sprint 4 (Burnup + Email) vem depois. Sistema de pontuação e plano canônico
estão em PLANO-DASHBOARD-PRODUTIVIDADE.md. Memória do Claude está em
~/.claude/projects/.../memory/MEMORY.md.
```

Aí o Claude novo lê os 2 arquivos, atualiza memória se precisar, e continua.

---

## 9. Riscos e mitigações ativos

| Risco | Status | Mitigação |
|---|---|---|
| Pesos virarem polêmica política | Não materializou | Shadow mode banner ativo, ajuste via PR no `complexity_weights.json` |
| Cron disputar `_state["running"]` | Sob controle | Cron usa endpoint separado, não toca lock global |
| Token Pipefy vazar | Sob controle | Env var no Render, nunca passa por navegador, nunca sai em log |
| Render free dorme e perde snapshots | Aceito | Documentado em seção 3.1. Quando virar dor, S3 |
| Líder não usar a ferramenta | Mitigação na Sprint 4 | Email diário força ponto de contato |
| Lista de pipes some no redeploy | Decisão pendente | Veja seção 3.2 |

---

## 10. Status final desta sessão

- Sprints 1 e 2 entregues e em produção.
- 208 pytest verde, 49 vitest verde.
- 3 commits novos no main: `315555a` (lideranca login), `bb61497` (Velocity), `728d3a2` (Debt + Cron).
- 4 arquivos `.md` versionados pra contexto: PLANO-DASHBOARD-PRODUTIVIDADE.md, HANDOFF-DASHBOARD.md, BRIEFING.md (handoff original), CHANGELOG-DEMO.md.
- Pendência operacional: configurar 5 secrets/envs descritos na seção 2 deste documento.

Próxima sessão começa pela Sprint 3 com snapshots já acumulados (assumindo cron rodando esta semana).
