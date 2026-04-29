# Pipefy Validator (Demo)

Compara a estrutura de pipes do Pipefy entre dois ambientes via API GraphQL para detectar drift de configuração antes que vire incidente em produção. Equivalente a um **Terraform Plan para o Pipefy**.

Este repositório é um **demo público** da ferramenta. Cada usuário traz seus próprios tokens.

---

## O que faz

- **Single-env**: compara 2 pipes dentro do mesmo ambiente (caso clássico: copia que precisa ficar idêntica à origem).
- **Cross-env**: compara o mesmo pipe (ou pipes diferentes) entre 2 ambientes (HMG vs PRD, ou organizações distintas).
- **Snapshot**: congela o estado de um pipe em JSON para usar como baseline em comparações futuras.
- **Batch**: roda self-check em vários pipes em sequência.
- **iPaaS**: valida flows do Activepieces (módulo separado).
- **Health Check**: diagnóstico das camadas da ferramenta.

---

## Stack

- **Robot Framework 7+** (RequestsLibrary + JSONLibrary) para extração e comparação
- **Python 3.11 + Flask** servindo dashboard e API (porta 8080)
- **Docker Compose** com volumes para `config/`, `results/`, `snapshots/`, `proposals/`
- **Pipefy GraphQL API**
- **Activepieces REST API** (módulo iPaaS)
- **Frontend vanilla** (sem framework)

---

## Setup local

### Pré-requisitos
- Docker Desktop
- Python 3.11
- Node.js LTS
- PowerShell (Windows) ou bash (Linux/Mac)

### Passos

1. Clone o repositório:
   ```powershell
   git clone https://github.com/fourd-qa/pipefy-validator-demo.git
   cd pipefy-validator-demo
   ```

2. Configure ambientes (cole seus tokens):
   ```powershell
   Copy-Item config\environments.example.json config\environments.json
   # Edite environments.json e preencha "Bearer SEU_TOKEN_AQUI" com tokens reais
   ```

3. Suba o container:
   ```powershell
   docker-compose up --build -d
   Start-Process http://localhost:8080
   ```

4. Rode os testes:
   ```powershell
   .\run-all-tests.ps1
   ```

---

## Estrutura

```
pipefy-validator-demo/
├── server.py                        Flask: dashboard + API
├── config/
│   ├── environments.example.json    Template (copie para environments.json)
│   ├── batch_pipes.json             Pares de pipes para batch validation
│   └── *.robot                      Presets gerados pela UI (gitignored, contêm tokens)
├── resources/
│   ├── queries/*.graphql            Queries Pipefy
│   └── keywords/*.resource          Keywords Robot
├── tests/
│   ├── *.robot                      Suítes de teste de validação
│   ├── python/                      pytest (45 testes do server)
│   └── frontend/                    vitest (35 testes de utils)
├── snapshots/                       Baselines JSON salvos
├── proposals/                       Iterações de design (mount opcional)
├── web/designs/                     Frontend V2 (HTML + CSS + JS vanilla)
├── Dockerfile + docker-compose.yml
└── run-all-tests.ps1                Roda pytest + vitest + smoke
```

---

## Rotas

| URL | Descrição |
|-----|-----------|
| `/` | Redirect para `/v2/configuracao` |
| `/v2/configuracao` | Tela de entrada (6 modos) |
| `/v2/execucao` | Polling + stepper + log streaming |
| `/v2/resultados` | Lista de divergências + diff side-by-side |
| `/v2/docs` | Documentação interna |
| `/v2/help` | FAQ + atalhos |
| `/api/run` | POST: dispara validação |
| `/api/status` | GET: estado da run em curso |
| `/api/results` | GET: validations.json |

---

## O que é comparado

### Estrutura
Fases (nomes, existência) · Campos por fase (id, label, tipo, obrigatoriedade, opções) · Start form · Labels.

### Automações
Status (ativa/inativa), tipo de ação, tipo de evento, fase destino (por nome), URL webhook, HTTP method/body/headers, fase do evento, conditions (operador + valor legível).

### Categorias filtráveis
SF (Start Form), FA (Fases & Campos), LB (Labels), AS (Auto Status), AD (Auto Fase Destino), AH (Auto HTTP), AC (Auto Condition). Também IF/IT/IS para iPaaS.

---

## Suítes de teste

```powershell
.\run-all-tests.ps1
```

Output esperado:
- pytest: ~45 testes (`tests/python/`)
- vitest: ~35 testes (`tests/frontend/`)
- smoke: 14 testes Robot (`tests/smoke_api.robot`, precisa container ativo)

---

## Segurança

- **Tokens nunca commitados**: `config/environments.json` e `config/*.robot` estão no `.gitignore`.
- **Endpoint sanitizado**: `/api/v2/environments` retorna `has_token: bool` em vez do token real.
- **Próximo passo**: tokens client-side via localStorage (cada usuário cola o próprio Bearer no navegador, backend não persiste).

---

## Deploy público (Render)

Este repo inclui `render.yaml` (Infrastructure-as-Code). Pra deploy:

1. Criar conta gratuita em https://render.com (login com GitHub).
2. **New > Blueprint** apontando pra este repo. Render detecta `render.yaml` e cria o serviço.
3. No prompt de env vars, definir `APP_PASSWORD` (qualquer string, vai proteger o app via Basic Auth). `APP_USERNAME` default `demo`.
4. Build leva ~3min (Docker). Healthcheck em `/healthz`.
5. URL final: `https://pipefy-validator-demo.onrender.com` (ou o slug que escolher).

Após online, abre a URL, navegador pede usuário/senha (Basic Auth), depois aparece o modal **"Configure seu primeiro ambiente"** pra colar o Bearer Pipefy.

Free tier do Render hiberna após 15min sem tráfego. Primeiro request após hibernação leva ~30s pra acordar. Suficiente pra demo.

---

## Licença

MIT.
