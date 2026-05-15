# Handoff — Dashboard de Produtividade

Documento pra retomar o trabalho num chat novo sem perder contexto.
Última atualização: 2026-05-15, fim de sessão. Sprints 1, 2, 3 e 4 (parte Burnup) entregues.

---

## TL;DR

- **Onde estamos**: Sprints 1, 2, 3 e a parte Burnup da Sprint 4 do `PLANO-DASHBOARD-PRODUTIVIDADE.md` no ar. Falta da Sprint 4: email diário via Resend.
- **Repositório**: `fourd-qa/pipefy-validator-demo` (público), branch `main`.
- **Deploy**: Render free tier. URL `https://pipefy-validator-demo.onrender.com`.
- **Testes**: 260 pytest + 49 vitest verdes (Sprint 4 adicionou 34 pytest novos).
- **Login**: `lideranca / lideranca` vê o dashboard. `demo / <APP_PASSWORD>` continua usando o validador normal sem ver o dashboard.
- **Massa demo**: `scripts/seed_dashboard_snapshots.py` gera 20 snapshots fictícios (10/pipe × 2 pipes HMG/PRD) + 1 blueprint demo no PRD com gap ~75-85% pra Sprint 4 mostrar progresso offline.

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

### 1.4 Sprint 3 — Hot Spots + Lead Time

**Engine** (em `dashboard_metrics.py`, segue padrão da Sprint 1):
- `compute_hotspots(snapshots_root, pipe_id, weights_path)`: ordena snapshots por timestamp, faz diff entre pares consecutivos, agrega por phase. Detecta phase create/delete/rename, field create/delete/type/required em phase, mudanças no start form. Score = soma dos pesos das mudanças. Level CLEAN/LOW/MEDIUM/HIGH classifica score.
- `compute_leadtime(snapshots_root, monitored)`: pareia pipes monitorados pelo nome base ignorando sufixos (HMG/PRD/(demo)). Pra cada par, calcula primeira aparição de phases e fields em cada lado, lag = diff em dias úteis. Filtra baseline pré-existente (elementos no t0 dos dois lados) pra não enviesar mediana.

**Endpoints**:
- `GET /api/dashboard/hotspots?pipe_id=...` (gated lideranca): default usa primeiro pipe enabled.
- `GET /api/dashboard/leadtime` (gated): retorna todos os pares HMG/PRD com mediana, média, máximo e listas de promovidos/pendentes.
- `/api/dashboard/data` foi expandido pra incluir `hotspots` e `leadtime` no payload agregado.

**UI** (cards Hot Spots e Lead Time substituem os stubs):
- Hot Spots: barra colorida por level + score numérico + samples expansíveis (clique na linha) com kind, peso e detalhe da mudança.
- Lead Time: 3 KPIs (mediana global, média, total promovidos) + por par mostra contadores baseline/promovidos/pendentes e lista das promoções com cor (verde <3d, laranja 3-4d, vermelho ≥5d).

**Massa demo** (`scripts/seed_dashboard_snapshots.py`):
- Gera 20 snapshots fictícios (10/pipe × 2 pipes) ao longo de 14 dias úteis terminando em 2026-05-05.
- 1 par HMG/PRD ("Mesa de Crédito PF") com evolução determinística em 7 estados (v1→v7).
- Cenário verificado: phase "Análise de Crédito" acumula 4 mudanças (MEDIUM), phase "Validação de Renda" 1 mudança (LOW), Start Form 1 mudança. Lead time mediano 3d úteis, máximo 4d, 6 elementos promovidos, 0 pendentes.
- Idempotente: `python scripts/seed_dashboard_snapshots.py` recria. `--dry-run` simula. `--no-monitored` não toca a config.

**Testes**: `tests/python/test_dashboard_sprint3.py` (18 casos: engine + endpoints + integração `/api/dashboard/data`).

### 1.5 Sprint 4 — Burnup vs Blueprint

**Engine** (em `dashboard_metrics.py`):
- `load_blueprint / save_blueprint / delete_blueprint`: persistem snapshot-meta em `snapshots/blueprints/<pipe_id>.json`. Estrutura: `{marked_at, source_snapshot, snapshot}`.
- `compute_burnup(snapshots_root, blueprints_root, pipe_id)`: compara o snapshot mais recente do pipe contra o blueprint marcado. Cobertura por categoria (phases / phase_fields / start_form_fields) — itens extras no atual NÃO penalizam (podem ser features fora do escopo da migração). Overall pct = média ponderada por total de itens.

**Endpoints**:
- `GET /api/dashboard/burnup?pipe_id=...` (gated lideranca): default usa primeiro pipe enabled.
- `GET /api/dashboard/blueprint?pipe_id=...` (gated): metadata do blueprint marcado (sem o snapshot completo).
- `POST /api/dashboard/blueprint` (gated, body `{pipe_id, snapshot_filename}`): marca snapshot existente em `snapshots/auto/<pipe>/` como blueprint. Valida `snapshot_filename` contra path traversal.
- `DELETE /api/dashboard/blueprint?pipe_id=...` (gated): remove blueprint.
- `/api/dashboard/data` foi expandido pra incluir `burnup` no payload agregado.

**UI** (card Burnup substitui o stub):
- Picker próprio pra escolher pipe entre os monitorados.
- KPI grande do `overall_pct` colorido por faixa (CLEAN ≥90, LOW ≥70, MEDIUM ≥50, HIGH <50).
- 3 barras de cobertura: phases / phase_fields / start_form, cada uma expansível pra mostrar lista de itens missing com label legível ("Phase · Field" pra phase_fields).
- Estado vazio: botão "Marcar snapshot mais recente como blueprint" que automaticamente busca `/api/dashboard/auto-snapshots/<pipe>` e usa o primeiro arquivo.
- Estado marcado: botões "Remover blueprint" e "Re-marcar como snapshot atual".

**Massa demo** (`scripts/seed_dashboard_snapshots.py`):
- `_build_blueprint_state()`: gera v8 fictício partindo de v7 com 1 phase nova ("Documentação Final" com 2 fields) + 3 fields novos em phases existentes + 2 fields novos no start form.
- `_write_blueprint_demo()`: grava `snapshots/blueprints/pipe-mesa-credito-prd.json` com formato igual ao do endpoint POST.
- Burnup do pipe PRD demo mostra cobertura ~75-85% (gap visível).

**Testes**: `tests/python/test_dashboard_sprint4.py` (34 casos: load/save/delete blueprint, compute_burnup com vários cenários, endpoints com gating + 400/404 + path traversal + fluxo end-to-end + integração `/api/dashboard/data`).

**Pendência da Sprint 4**: email diário via Resend (`POST /api/cron/daily-email` + template HTML + GitHub Actions cron) — ver seção 5 abaixo.

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
├── server.py                           +hotspots, +leadtime, +monitored-pipes, +cron, +dashboard endpoints
├── dashboard_metrics.py                engine pura: velocity, debt, hotspots, leadtime
├── config/
│   ├── complexity_weights.json         24 prefixos + multiplicadores
│   └── monitored_pipes.json            lista de pipes do cron (Sprint 3 adiciona 2 demos automaticamente)
├── snapshots/auto/                     histórico do cron (Sprint 3 popula via seed quando cron real ainda não rodou)
│   ├── pipe-mesa-credito-hmg/          10 snapshots demo (HMG)
│   └── pipe-mesa-credito-prd/          10 snapshots demo (PRD)
├── scripts/
│   └── seed_dashboard_snapshots.py     gerador determinístico da massa demo (NOVO Sprint 3)
├── web/designs/
│   ├── tela_dashboard.html             6 cards: Velocity, RunMeta, Monitored Pipes, Debt, Hot Spots, Lead Time
│   └── assets/v2_utils.js              renderDashboardLink() injetado nas 3 telas existentes
├── tests/python/
│   ├── test_dashboard.py               15 casos: whoami + gates + lideranca login
│   ├── test_dashboard_metrics.py       38 casos: scoring + endpoints velocity/debt
│   ├── test_dashboard_cron.py          19 casos: monitored-pipes + cron + auto-snapshots
│   └── test_dashboard_sprint3.py       18 casos: hotspots + leadtime + endpoints (NOVO)
└── .github/workflows/
    └── cron-snapshot.yml               cron */30 chama /api/cron/snapshot
```

---

## 5. Próximos passos: parte restante da Sprint 4 (email diário)

**Burnup** ✅ entregue (ver seção 1.5).

**Email diário** (pendente)
- Provider sugerido: **Resend** (free tier 100 emails/dia, API JSON simples).
- Env vars: `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO` (lista).
- Endpoint `POST /api/cron/daily-email` (mesmo padrão de auth do cron snapshot, com `X-Cron-Token`).
- GitHub Actions cron `0 18 * * 1-5` chama o endpoint.
- Template HTML enxuto: 4 KPI cards (Velocity, Debt, Lead Time, Burnup %) + alertas (hot spots novos, churn detectado, queda no Burnup).
- Testes mockando Resend API.

**Estimativa**: 8-10h.

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
Lê o HANDOFF-DASHBOARD.md desta pasta. Sprints 1, 2 e 3 do Dashboard de
Produtividade estão entregues. Próximo passo: Sprint 4 (Burnup + Email).
Sistema de pontuação e plano canônico estão em PLANO-DASHBOARD-PRODUTIVIDADE.md.
Memória do Claude está em ~/.claude/projects/.../memory/MEMORY.md.
Pra rebootar massa demo localmente: python scripts/seed_dashboard_snapshots.py
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

- Sprints 1, 2, 3 e Burnup da Sprint 4 entregues. Sprints 1 e 2 em produção; Sprints 3 e 4 já no `main` mas rodam offline com massa demo até o cron real começar a coletar.
- 260 pytest verdes, 49 vitest verdes.
- Sprint 4 adicionou: `dashboard_metrics.py` (load/save/delete_blueprint + compute_burnup), 4 endpoints (`/api/dashboard/burnup` + GET/POST/DELETE `/api/dashboard/blueprint`), card Burnup completo na UI, 34 pytest, blueprint demo determinístico no seed.
- Pendência operacional: os 5 secrets/envs da seção 2 continuam pendentes. Quando configurados, o cron vai sobrescrever a massa demo com snapshots reais — o engine aceita os dois formatos.
- Decisão pendente herdada: persistência do `monitored_pipes.json` no Render free tier (seção 3.2).
- Decisão nova: persistência do `snapshots/blueprints/` no Render free tier — mesmo problema do `monitored_pipes.json`, mas blueprints são raros (1 marcação por iniciativa de migração). Aceitável re-marcar após hibernação.

Próxima sessão: parte restante da Sprint 4 (email diário Resend).
