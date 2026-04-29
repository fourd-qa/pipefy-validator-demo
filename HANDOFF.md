# PIPEFY VALIDATOR (DEMO) — HANDOFF

Documento canônico do projeto. Se algo aqui contradiz o código, **a verdade é o código atual**.

Última atualização: 2026-04-29 (sanitização inicial pra demo público).

---

## 1. CONTEXTO

Demo público da ferramenta Pipefy Validator. Repositório aberto, sem credenciais de cliente real, apto a deploy em Render/Fly/Railway.

A versão privada (com integrações de cliente) vive em pasta separada e não é referenciada aqui.

---

## 2. PREFERÊNCIAS DE COMUNICAÇÃO (não violar)

1. **NUNCA usar travessão (—)** em respostas. Use vírgula, ponto, frases curtas.
2. Foco no código, sem introduções genéricas.
3. Comandos PowerShell prontos pra copiar quando entregar arquivos.
4. PowerShell heredoc com aspas simples: `@'...'@`.
5. Porta do projeto: **8080**.
6. `VERIFY_SSL=false` em todos os ambientes (proxy corporativo).
7. Avisar antes de mexer em arquivos de volume mount (`config/`, `snapshots/`, `results/`, `proposals/`).
8. Respostas curtas e diretas.
9. Deploy automático após qualquer alteração que toque imagem (`docker-compose up --build -d`).

---

## 3. STATUS ATUAL

- **V2 é o padrão** servido em `/`. Não existe mais V1 (`/legacy` foi removido).
- Container Docker roda na porta 8080.
- Frente A+ completa: Single, Cross, Snapshot Gerar/Comparar, Batch, Categorias filtráveis, Cancel real, Health Check.
- **Tokens client-side** (Fase 2 completa): credenciais ficam em local/sessionStorage do navegador, backend nunca persiste. POST `/api/run` aceita token+base_url+org_id no body, gera `config/active.robot` esterilizado no fim.
- **Basic Auth** opcional via `APP_PASSWORD` env var. `/healthz` sempre acessível.
- Modo dia/noite funcional (toggle no topo, persistência em localStorage).
- Pasta `proposals/` com volume mount para iterações de design.
- Suíte de testes: 67 pytest + 49 vitest + 15 smoke Robot.

---

## 4. STACK

- Robot Framework 7+ (RequestsLibrary + JSONLibrary)
- Docker (python:3.11-slim) + docker-compose
- Flask (porta 8080) servindo: V2 (`/`, `/v2/*`), API (`/api/*`), docs, help, propostas, reports
- Pipefy GraphQL API
- iPaaS: Activepieces (REST API)
- Frontend vanilla (sem framework). CSS/JS externos em `/v2/assets/*`
- Tipografia: Inter (UI), JetBrains Mono (IDs/UUIDs/código)

---

## 5. ESTRUTURA

```
pipefy-validator-demo/
├── HANDOFF.md                         ← este arquivo
├── BACKUP.md                          ← estratégia de backup
├── README.md                          ← entrada pública do repo
├── server.py                          ← Flask
├── pytest.ini
├── package.json                       ← vitest
├── requirements.txt
├── requirements-dev.txt
├── run-all-tests.ps1                  ← roda os 3 stacks
├── Dockerfile
├── docker-compose.yml
│
├── config/                            VOLUME MOUNT
│   ├── environments.example.json      ← template (copiar para environments.json)
│   ├── batch_pipes.json               ← pares de pipes para batch
│   ├── active.robot / active_cross.robot ← copiados pelo /api/run
│   └── *.robot                        ← presets gerados pela UI (gitignored, contêm token)
│
├── resources/
│   ├── queries/*.graphql
│   ├── keywords/
│   │   ├── api_session.resource
│   │   ├── ipaas_session.resource
│   │   ├── comparator.resource        ← keyword Categoria Habilitada (SF/FA/LB/AS/AD/AH/AC)
│   │   └── ipaas_comparator.resource  ← keyword Categoria iPaaS Habilitada (IF/IT/IS)
│   ├── libraries/ProgressLibrary.py
│   └── schema_baseline.json
│
├── tests/
│   ├── comparar_pipes.robot           ← CT01-CT04 (single)
│   ├── comparar_cross.robot           ← CT-CROSS-01 (cross)
│   ├── snapshot.robot                 ← CT05 (gerar) + CT06 (comparar)
│   ├── batch.robot                    ← CT-BATCH com BATCH_ENV + BATCH_SELECTED
│   ├── healthcheck.robot              ← HC-01..HC-09
│   ├── ipaas_validation.robot         ← CT-IPAAS-01..04
│   ├── schema_canary.robot            ← CT07
│   ├── smoke_api.robot                ← Smoke HTTP do Flask
│   ├── python/                        ← pytest (45 testes)
│   └── frontend/                      ← vitest (35 testes)
│
├── snapshots/                         VOLUME MOUNT (baselines JSON)
├── results/                           VOLUME MOUNT (validations.json, log.html)
├── proposals/                         VOLUME MOUNT (entregas do designer)
└── web/designs/                       V2
    ├── tela_configuracao_v1.html
    ├── tela_execucao_v1.html
    ├── tela_resultados_v1.html
    ├── docs.html / help.html
    └── assets/
        ├── tela_*.css / tela_*.js
        ├── v2_utils.js                ← funções puras compartilhadas (testáveis em Node)
        ├── v2_theme.css / v2_theme.js ← modo dia/noite
```

---

## 6. AMBIENTES (template público)

`config/environments.example.json` traz dois esqueletos:

| ID | Tipo | Status |
|----|------|--------|
| `fourd_hmg` | Pipefy bearer | Template, edite com seu token |
| `ipaas_fourd` | Activepieces bearer | Template iPaaS |

O usuário copia o arquivo para `environments.json` e preenche tokens reais. `environments.json` está no `.gitignore`.

Tokens podem expirar. Activepieces tipicamente expira em ~7 dias. Renove via UI da plataforma ou direto no `environments.json`.

---

## 7. ROTAS V2

| URL | Função |
|-----|--------|
| `/` | Redirect 302 → `/v2/configuracao` |
| `/v2/configuracao` | Tela de entrada (6 modos: Single, Cross, Snapshot, Batch, iPaaS, Health Check) |
| `/v2/execucao` | Polling + stepper + log streaming |
| `/v2/resultados` | Lista de divergências + donut + diff side-by-side |
| `/v2/docs` | Documentação |
| `/v2/help` | FAQ + atalhos |
| `/v2/assets/<file>` | CSS/JS com `no-cache` |
| `/proposals/` | Índice de iterações de design |
| `/api/run` POST | Dispara validação |
| `/api/run/cancel` POST | Mata o subprocess Robot |
| `/api/status` | Polling (running, finished, exit_code, progress, logs) |
| `/api/results` | Conteúdo de `validations.json` |
| `/api/configs` GET | Lista presets single + cross |
| `/api/configs` POST | Cria novo `cross_*.robot` a partir de 2 envs |
| `/api/environments` | V1-compat (com tokens, será removido na Fase 2) |
| `/api/v2/environments` | Sanitizado (sem tokens, com `has_token`) |
| `/api/environments` POST | Salva/atualiza ambiente |
| `/api/environments/<type>/<id>` DELETE | Remove ambiente |
| `/api/snapshots` | Lista snapshots disponíveis |
| `/api/batch` | Conteúdo de `batch_pipes.json` |
| `/reports/<file>` | Robot Framework reports |

---

## 8. DECISÃO ARQUITETURAL D → A+

A decisão D (MVP Honesto) escondia controles que o backend ignorava. A frente A+ destrava esses controles propagando os parâmetros via `--variable` para o Robot.

**Status A+ por modo:**

| Modo | Pipe override | Categorias | Outros |
|------|---------------|------------|--------|
| Single-env | ✅ `pipe_origem_uuid` + `pipe_destino_uuid` | ✅ `CATEGORIES_FILTER` | — |
| Cross-env | ✅ Idem + dropdowns dinâmicos | ✅ Idem | — |
| Snapshot Gerar | ✅ `pipe_uuid` → `PIPE_ORIGEM_UUID` | n/a | Label auto-gerado |
| Snapshot Comparar | ✅ `pipe_uuid` → `PIPE_DESTINO_UUID` | ✅ herda comparator | Pipe live escolhível |
| Batch | ✅ `BATCH_SELECTED` (seleção UI) | ✅ idem | `BATCH_ENV` filtra por env |
| iPaaS | n/a | ✅ tags IF/IT/IS | Healthcheck integrado |
| Health Check | n/a | n/a | Roda HC-01..HC-09 |

### Helpers no `server.py`

- `_pipe_override_vars(data)` → constrói lista `--variable PIPE_*_UUID/REPO_ID`
- `_categories_var(data)` → `--variable CATEGORIES_FILTER:CSV`. Detecta "todas selecionadas" e omite filtro
- `_extract_fail_from_output_xml()` → parsea `output.xml` do Robot pra mensagem útil + hint (401, PERMISSION_DENIED, 404, timeout)
- `_generate_cross_robot(src_env, dst_env)` → monta `cross_*.robot` com prefixos `ORIGEM_/DESTINO_`

---

## 9. ROADMAP

### Concluído (abril 2026)

- [x] **Tokens client-side** completo. Vault em `localStorage[pv-vault-v1]` + `sessionStorage` (toggle "Lembrar"). Backend rejeita 400 sem token.
- [x] **Basic Auth** via `APP_PASSWORD` env var. `/healthz` exempt pra liveness probe.
- [x] **Tela inicial** "Cole seu Bearer" quando vault vazio.
- [x] **Indicador "Conectado"** no header com link pra Gerenciar Ambientes.
- [x] **Esterilização** de `config/active*.robot` no `finally` da run.
- [x] Endpoints legacy (`/api/environments`, `/api/configs POST`) → 410 Gone.

### Pendente (Fase 3 — deploy público)

- [ ] **Deploy Render** (free tier, Docker, HTTPS automático). Env vars: `APP_PASSWORD`, `APP_USERNAME`.
- [ ] Criar repo público `fourd-qa/pipefy-validator-demo` e fazer initial push.
- [ ] Configurar Render webhook pra autobuild no push pra `main`.

### Pendente (médio prazo)

- [ ] **Multi-user real**: hoje `_state["running"]` bloqueia 2 runs simultâneas. Pra escalar, mover `config/active.robot` pra `tmp/<run_id>/active.robot` e variabilizar `Resource` nos `.robot` tests (passar via `--variablefile`).
- [ ] CI via GitHub Actions rodando `run-all-tests.ps1`.
- [ ] iPaaS com Cross-env real (hoje só self-check + snapshot).
- [ ] Audit de UX visual depois das propostas do designer.

### Segurança aberta

- [ ] Sanitizar f-string injection em `_generate_robot()` (token com aspas/quebras escapa para `.robot`). Hoje `_escape_robot_value` remove `\n\r` mas não escapa todas as edge cases.
- [ ] Rate limiting em `/api/run` pra evitar abuso após Basic Auth.

---

## 10. SUÍTES DE TESTE

### pytest

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/python/
```

Cobre funções puras (`_generate_robot`, `_extract_fail_from_output_xml`, `_categories_var`, `_pipe_override_vars`, `_load_envs`, `_save_envs`, `_generate_cross_robot`) + endpoints HTTP completos com `subprocess.Popen` mockado.

### vitest

```powershell
npm install
npm test
```

Cobre utils de `web/designs/assets/v2_utils.js`: slugify, escapeHtml, parseCrossConfigMeta, getCrossTokenStatus, computeSuggestedSnapLabel, categorize, severityOf, truncMid.

### smoke Robot

```powershell
docker-compose up -d
python -m robot --outputdir results/smoke -t "HC-*" tests/smoke_api.robot
```

Cobre: redirect raiz, V2 (configuracao/docs/help), `/api/configs`, `/api/v2/environments` (sanitização), `/api/snapshots`, `/api/batch`, `/api/results`, `/api/status`, POST `/api/run` defensivo, no-cache nos assets V2.

### Rodar tudo

```powershell
.\run-all-tests.ps1
```

Flag `-SkipSmoke` pula Robot quando container offline.

---

## 11. DEPLOY E ROLLBACK

### Comando padrão

```powershell
cd C:\Users\FourD\Documents\robothz\pipefy-validator-demo
docker-compose down
docker-compose up --build -d
Start-Sleep -Seconds 8
Start-Process "http://localhost:8080"
```

### Volume mount (sem rebuild)

`config/`, `results/`, `snapshots/`, `proposals/`

### Imagem (precisa rebuild)

`server.py`, `web/`, `resources/`, `tests/`

---

## 12. TROUBLESHOOTING

| Sintoma | Causa | Fix |
|---------|-------|-----|
| Run falha 401 Unauthorized | Token expirou | Renove via Gerenciar Ambientes |
| PERMISSION_DENIED | Token sem permissão no pipe | Use outro pipe ou outro token |
| `/api/run` 409 | Run em execução | Aguarde ou clique Cancel |
| Mock zumbi na Resultados | Run abortou sem `validations.json` | Backend grava fallback EXECUTION_FAILED automaticamente |
| Mudança em `config/` não aparece | Cache navegador | `Ctrl+F5` |
| `/v2/*` 404 | Container rodando versão antiga | `docker-compose up --build -d` |
| Cache buildx Docker corrompido | Snapshot não encontra parent | `docker system prune -f` antes do rebuild |
| Toggle dia/noite não responde | localStorage com valor antigo | DevTools console: `localStorage.clear(); location.reload()` |

---

## 13. PRÓXIMAS SESSÕES

### Antes de tocar código

1. Leia este HANDOFF inteiro
2. Confirme `docker-compose ps` mostra container up. Se não, `docker-compose up --build -d`
3. Rode `.\run-all-tests.ps1` pra garantir baseline verde
4. Veja `git status`

### Padrão de comunicação obrigatório

- Sem travessão. Use vírgula, ponto, frases curtas
- Respostas curtas e diretas, sem introdução
- Quando entregar arquivos: comando PowerShell pronto pra copiar
- Quando deploy: rebuild automático sem perguntar (`docker-compose up --build -d`)

### Quando atacar item novo

1. Cheque o roadmap (seção 9)
2. Volume mount = sem rebuild, imagem = rebuild
3. Implemente, rebuild, rode os testes
4. Atualize a seção apropriada deste HANDOFF
5. Avise no chat com 1 frase de resumo
