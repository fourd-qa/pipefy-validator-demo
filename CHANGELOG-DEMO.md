# CHANGELOG do trabalho na demo (pra portar pro `pipefy/` original)

Sessão 2026-04-29. Origem: pasta `pipefy-validator-demo/`. Destino: `pipefy/`.

Lista canônica do que mudou. Cada item indica:
- **Onde**: arquivo/função
- **O que**: mudança
- **Por quê**: motivação
- **Risco no port**: se quebra algo no original ou requer ajuste

---

## 1. Tokens client-side (mudança estrutural maior)

**Por quê:** pasta original guarda tokens em `environments.json` plaintext + `.robot` files com Bearer hardcoded. Demo público não pode persistir tokens. Solução: navegador guarda token, manda no body de cada `/api/run`.

**Risco no port:** ALTO. Se portar tudo, perde fluxo atual de "Gerenciar Ambientes" salvar no servidor. Avalie se quer migrar TODO o backend ou manter feature flag (server-side hoje + client-side opcional).

### Backend (`server.py`)

**Adicionado:**
- `_extract_pipefy_creds(data, prefix='')` — extrai `token`, `base_url`, `org_id`, `auth_mode`, `verify_ssl`, `session_cookie`, `csrf_token` do body. Suporta prefixos `''`, `src_`, `dst_` pra cross-env.
- `_extract_ipaas_creds(data)` — análogo pra iPaaS (`ipaas_token`, `ipaas_base_url`, `ipaas_project_id`).
- `_normalize_token(raw)` — aceita "Bearer xxx" ou "xxx", retorna sempre "Bearer xxx".
- `_escape_robot_value(s)` — remove `\r\n` (mitiga injection básica em Variables).
- `_build_pipe_lines(data, prefix_origem, prefix_destino)` — gera linhas Variables de UUIDs/repo_id.
- `_generate_cross_robot_runtime(src_creds, dst_creds, data)` — substitui `_generate_cross_robot(src_env, dst_env)` (que lia de envs persistidos).
- `_sterilize_active_robots()` — no `finally` da thread de `/api/run`, sobrescreve `config/active.robot`, `active_cross.robot`, `ipaas_fourd.robot` com placeholders sem token. Mitiga leak via filesystem.
- Constantes `_STERILE_PIPEFY_ROBOT`, `_STERILE_CROSS_ROBOT`, `_STERILE_IPAAS_ROBOT`.

**Modificado:**
- `_generate_robot(env)` → `_generate_robot(creds, data)` — assinatura nova. Recebe creds extraídos do body em vez de env dict.
- `_generate_ipaas_robot(env)` → `_generate_ipaas_robot(creds)` — análogo.
- `/api/run`: validação de credenciais no início (rejeita 400 se token+base_url ausentes pra single/cross/snapshot/batch/ipaas; healthcheck é exceção e roda sem token).

**Removido:**
- `_load_envs()`, `_save_envs()` — não persistimos mais envs.
- `_generate_cross_robot(src_env, dst_env)` — substituído pelo `_runtime`.
- Entire body do `save_environment()`, `delete_environment()`, `get_environments_safe()`, `create_cross_config()` — viraram stubs 410 Gone.

**Endpoints DEPRECATED → 410 Gone:**
- `GET /api/environments`
- `GET /api/v2/environments`
- `POST /api/environments`
- `DELETE /api/environments/<type>/<id>`
- `POST /api/configs`

**Endpoint que ficou deprecated mas retorna 200:**
- `GET /api/configs` — retorna `{single: [], cross: []}`. Frontend agora lê cross configs do localStorage; mantemos a rota pra não quebrar callers antigos.

### Frontend

**Adicionado em `web/designs/assets/v2_utils.js`:**
- `vaultList()`, `vaultSave(env)`, `vaultGet(id)`, `vaultRemove(id)`, `vaultClear()`, `vaultSanitized()` — localStorage (`pv-vault-v1`) ou sessionStorage baseado em `env.remember`.
- `buildRunPayload(mode, envIds, base)` — empacota credenciais corretas no payload do `/api/run`. Para `single/snapshot/batch`: `envIds = {src: 'fourd_hmg'}`. Para `cross`: `{src, dst}`. Para `ipaas`: `{ipaas: 'ipaas_fourd'}`.
- `apiFetch(url, options)` — wrapper de `fetch` que injeta `Authorization: Basic`. Em 401 limpa cred e re-prompta. Reusado em todas as 3 telas V2.
- `clearAppAuth()` — exposto pro frontend resetar Basic Auth.

**Adicionado em `web/designs/assets/tela_configuracao_v1.js`:**
- `loadEnvironmentsFromVault()` — recarrega `ENVS_DATA` a partir do localStorage (substitui fetch `/api/v2/environments`).
- `_readCrossConfigs()`, `_saveCrossConfigs()` — cross configs em `localStorage[pv-cross-configs-v1]`.
- `renderConnectedBadge()` — badge no header com nome do env ativo + count.
- `maybeShowOnboardingModal()`, `showOnboardingModal()` — modal forçado quando vault vazio.
- `_wireCrossAddBtn()` — extrai wiring do botão "Criar nova config cross" pra ser chamado mesmo quando lista cross é vazia.

**Modificado:**
- `loadEnvironments()` — agora síncrono (lê localStorage). Continua `async` pra preservar `.then()` callers.
- `fetchFullEnv(type, id)` — síncrono, lê do vault. Substitui antiga chamada `/api/environments`.
- `loadConfigs()` — lê localStorage em vez de `fetch /api/configs`.
- Modal Gerenciar Ambientes (delete/save handlers): chamam `vaultRemove`/`vaultSave` em vez de `fetch /api/environments`.
- `renderEnvForm()` — adicionado checkbox `_remember` ("Lembrar nesta máquina").
- `buildRunPayload()` — usa `V2Utils.buildRunPayload()` pra empacotar creds.
- `executeRun()` — trata 400 com mensagem específica "Configure um ambiente".
- `parseCrossConfigMeta()` em `v2_utils.js` reescrita pra ser genérica (cross_<src>_x_<dst> ou cross_<x>_selfcheck), removendo hardcodes de IDs do cliente.

---

## 2. Basic Auth no Flask (deploy público)

**Por quê:** demo público precisa de barreira mínima. Não é seguro o bastante pra produção real, mas evita scraping casual.

**Risco no port:** BAIXO. Feature está OFF por default (env var vazia = sem auth). Se você não setar `APP_PASSWORD`, original continua aberto como hoje.

### Backend (`server.py`)

**Adicionado:**
- Constantes `APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()` e `APP_USERNAME` (default `demo`).
- `_check_basic_auth()` — valida header `Authorization: Basic`. Retorna `Response 401` ou `None`.
- `_auth_challenge()` — Response 401 com `WWW-Autheticate`.
- `_global_auth()` — `@app.before_request` decorator que delega pra `_check_basic_auth`.
- `GET /healthz` — endpoint exempt de auth (pra liveness probe Render/K8s).

### Frontend

**Adicionado em `v2_utils.js`:**
- `apiFetch()` (já mencionado) — prompt na primeira chamada pede usuário/senha, salva em `sessionStorage[pv-app-auth-v1]`.

---

## 3. Descoberta automática de pipes (`/api/discover-pipes`)

**Por quê:** UX. Original obriga digitar UUID/repo_id manualmente. Agora frontend chama o endpoint que faz query GraphQL `organization(id) { pipes { id, uuid, name } }` e popula a lista.

**Risco no port:** BAIXO. Endpoint isolado, não toca em `/api/run` nem altera fluxo principal.

### Backend (`server.py`)

**Adicionado:**
- `POST /api/discover-pipes` — body `{token, base_url, org_id, verify_ssl?}`. Retorna `{ok, org_name, pipes:[{name, uuid, repo_id}], count}`. Trata 401 (token rejeitado), 502 (rede/upstream/GraphQL errors), 400 (validação).

### Frontend

**Adicionado em `tela_configuracao_v1.js`:**
- Bloco "Pipes" em `renderEnvForm` com botão **Buscar pipes da org**.
- Handler em `wireFormInsideModal` chama `apiFetch('/api/discover-pipes')`, mostra status inline, salva em `formEl.dataset.discoveredPipes`.
- Save handler usa `discoveredPipes` se setado, sobrescrevendo `env.pipes`.

---

## 3.1 Default env opcional (UX demo público)

**Por quê:** evitar fricção pro visitante do demo ter que gerar PAT antes de testar.

**Risco no port:** ZERO. Sem env var setada, comportamento original mantido (modal de onboarding pede dados manualmente).

### Backend (`server.py`)

- Constantes lidas no startup: `DEFAULT_PIPEFY_TOKEN`, `DEFAULT_PIPEFY_BASE_URL`, `DEFAULT_PIPEFY_ORG_ID`, `DEFAULT_PIPEFY_NAME`, `DEFAULT_PIPEFY_VERIFY_SSL`.
- Novo `GET /api/default-env`: retorna `{available: false}` se token vazio, ou `{available: true, name, token, base_url, org_id, verify_ssl, auth_mode}` se setado.
- Token volta no response em **claro** (esse é o ponto: cliente recebe pra preencher modal). Por isso só usar PAT de org sandbox dedicada.

### Frontend

- `tryLoadDefaultEnv(callback)` em `tela_configuracao_v1.js`.
- `showOnboardingModal` chama `tryLoadDefaultEnv` e pré-popula campos quando disponível, com banner indicando "Default carregado do servidor".

### `render.yaml`

- Novas env vars com `sync: false` pro PAT (Render pede no setup, não vai pro git).

---

## 4. Adaptação pra Render (deploy público)

**Por quê:** Render free tier exige `$PORT` env var, prefere gunicorn em vez de Flask dev server.

**Risco no port:** ZERO. Original pode continuar usando `python server.py`. Mudanças são aditivas (gunicorn é uma dep extra, env var tem fallback).

### Mudanças

**`requirements.txt`:**
- Adicionado `gunicorn>=21.0`.

**`server.py`:**
- `if __name__ == "__main__":` lê `os.environ.get("PORT", 8080)`.

**`Dockerfile`:**
- `ENV PORT=8080` + `EXPOSE 8080`.
- `CMD gunicorn server:app --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180 --access-logfile -`.
- `RUN mkdir -p results tmp`.

**`render.yaml` (novo):**
- IaC declarando o web service, healthCheckPath, env vars (`APP_PASSWORD` com `sync: false` pra Render pedir no setup).

**`.gitignore`:**
- Adicionado `tmp/`.

---

## 5. Bugs encontrados em produção (após deploy Render)

Lista de bugs reais que aconteceram online. Aplicar fixes correspondentes na pasta original.

### 5.1 TDZ em `_onboardingShown` (let antes do uso)

- **Sintoma**: `Uncaught ReferenceError: Cannot access '_onboardingShown' before initialization`. Modal de onboarding nunca aparecia. Vault ficava vazio. Executar dava "payload inválido".
- **Local**: `tela_configuracao_v1.js`, declaração da variável.
- **Fix**: trocar `let _onboardingShown = false;` por `var _onboardingShown = false;`. Function declarations sofrem hoisting; `let` não. Como a função `maybeShowOnboardingModal` é chamada por `loadEnvironments` lá em cima, a variável precisa estar acessível.

### 5.2 `escapeHtml` indefinido em `renderConnectedBadge`

- **Sintoma**: `ReferenceError: escapeHtml is not defined`. Travava `loadEnvironments`.
- **Local**: `tela_configuracao_v1.js` linha que chama `renderConnectedBadge`.
- **Fix**: usar `escapeHtmlInline` (função local) em vez de `escapeHtml` (que só existe em V2Utils).

### 5.3 HTMLs não carregavam `v2_utils.js`

- **Sintoma**: ao salvar no modal de onboarding, alert "V2Utils não disponível".
- **Local**: `web/designs/tela_configuracao_v1.html`, `tela_execucao_v1.html`, `tela_resultados_v1.html`.
- **Fix**: adicionar `<script src="/v2/assets/v2_utils.js"></script>` ANTES do script da tela.

### 5.4 Botão "Criar nova configuração cross-env" não reagia

- **Sintoma**: clique não fazia nada quando lista de cross configs estava vazia.
- **Local**: `populateCrossCards()` retornava cedo no caso vazio, antes de wirear `.cross-add`.
- **Fix**: extrair wiring pra helper `_wireCrossAddBtn()` chamado em ambos os caminhos (vazio e com lista).

### 5.5 Modal Gerenciar Ambientes não atualizava após onboarding

- **Sintoma**: usuário completava o onboarding, mas o modal Gerenciar continuava mostrando lista vazia.
- **Fix**: `openModal()` chama `populateEnvModal()` antes de abrir. `showOnboardingModal()` também chama após `vaultSave`.

### 5.6 Scrollbar invisível em dropdowns com muitos items

- **Sintoma**: dropdown de pipes com 11 items não mostrava scrollbar visível. User só conseguia navegar com setas.
- **Local**: `tela_configuracao_v1.css` `.dd-menu-inner`.
- **Fix**: aumentar `max-height` pra `420px`, adicionar `scrollbar-width: thin`, `scrollbar-color`, e `::-webkit-scrollbar-thumb` com cor accent (mais visível). Adicionar `overscroll-behavior: contain` pra wheel não vazar.

### 5.7 Texto desinformante no dialog "Criar cross"

- **Sintoma**: dialog dizia "Gera config/cross_<id>.robot" mas isso não acontece mais (cross é client-side).
- **Fix**: trocar texto pra explicar que combina dois envs do vault, credenciais vão no body do `/api/run` na execução.

### 5.8 Robot Framework IF com `'${var}'` quebra com payloads contendo `{}`

- **Sintoma**: `Invalid IF condition: Evaluating expression 'True and \\'{...}\\' != \\'{...}\\''`. Acontecia em **Snapshot Comparar** quando o pipe tinha automação com mutation GraphQL (body contém `%{428313830}` ou JSON `{...}`).
- **Local**: `resources/keywords/comparator.resource`, 6 linhas (URL, method, body, headers, phase destino, phase do evento).
- **Causa**: `IF '${body_orig}' != '${body_dest}'` interpola o valor dentro de string. Robot tenta resolver `%{...}` e `${...}` como variável, falhando.
- **Fix**: trocar pra sintaxe Python direta:
  ```robot
  IF    ${run_ah} and $body_orig != $body_dest and ($body_orig != '' or $body_dest != '')
  ```
  `$var` (sem chaves) em IF expression dá acesso direto à variável Python sem stringificação.
- **Risco no port**: BAIXO. Comportamento idêntico, só mais robusto. Aplicar nos arquivos `comparator.resource` e talvez `ipaas_comparator.resource` se tiver pattern similar.
- **Bug provavelmente preexistente** no projeto original, só dispara quando o pipe tem automação HTTP cuja body é literal com chaves.

---

## 6. Sanitização do código (preexistente, mas pode portar princípios)

Cliente real foi removido das strings/IDs. Não precisa portar (na pasta original cliente real continua). Mas:

- Snapshots de cliente movidos pra fora do repo (.gitignore continua excluindo `environments.json`).
- `web/index.html` (V1 legacy ~80KB) deletado. Rota `/legacy` removida. **Avalie se quer remover no original também** ou manter como fallback.

---

## 7. Testes adicionados

Suíte cresceu de 45 pytest pra 85 pytest, e 35 vitest pra 49 vitest. **Recomendado portar todos**, mesmo que não use a feature de tokens client-side.

### pytest novos (`tests/python/test_server_endpoints.py` + `test_server_units.py`)

- `_normalize_token` (4 cases: bearer, sem prefixo, case insensitive, vazio)
- `_escape_robot_value` (newlines, None)
- `_extract_pipefy_creds` (completo, sem token, sem base_url, prefix src_, normaliza token)
- `_extract_ipaas_creds` (completo, sem token)
- `_generate_robot(creds, data)` (token, uuids, verify_ssl, sem pipes)
- `_generate_cross_robot_runtime` (2 tokens prefixados)
- `/api/run` (rejeita sem token, sem base_url, esteriliza após run)
- `/api/run` cross (rejeita sem dst, gera active_cross com 2 tokens)
- `/api/run` ipaas (rejeita sem token, gera ipaas_fourd.robot)
- `/api/run` healthcheck (sem token OK)
- `/api/discover-pipes` (200, 400 sem token, 400 sem org_id, 401, 502 GraphQL errors, 502 network, filtra pipes incompletos, body truncado)
- `/api/environments` deprecated 410 (GET/POST/DELETE)
- `/api/v2/environments` deprecated 410
- `/api/configs POST` deprecated 410
- Basic Auth (com/sem APP_PASSWORD, custom username, password whitespace-only)
- `/healthz` (sempre 200, mesmo com auth)
- Edge cases: token sem prefixo Bearer, token com `\n`, body inválido sem 500, mode desconhecido cai single, cancel sem process

### vitest novos (`tests/frontend/v2_utils.test.js`)

- `vaultList`, `vaultSave` (localStorage vs sessionStorage)
- `vaultSave` migra entre stores quando `remember` muda
- `vaultGet`, `vaultRemove`, `vaultClear`
- `vaultSanitized` (não expõe token, marca `has_token`)
- `buildRunPayload` (single, cross prefixos src_/dst_, ipaas, healthcheck sem creds, mescla campos extras, env id inexistente)
- `parseCrossConfigMeta` reescrita (selfcheck, cross_<src>_x_<dst>, fallback)

---

## 8. Limitações conhecidas (pra atacar depois, ou aceitar)

- **Concorrência multi-user**: hoje `_state["running"]` global bloqueia 2 runs simultâneas. `config/active.robot` é compartilhado. Solução futura: mover pra `tmp/<run_id>/active.robot` e variabilizar `Resource` nos `.robot` tests via `--variablefile`.
- **Pipefy GraphQL injection**: `_escape_robot_value` só remove newlines. Token com `${` ou `}` pode injetar variáveis Robot. Risco baixo (atacante precisa controlar token), mas vale endurecer.
- **No retry no /api/run**: se Pipefy GraphQL retornar 503 transient, run aborta. Adicionar retry com backoff seria útil pra demo confiável.
- **Render free tier hiberna após 15min**: primeiro request leva ~30s pra subir. Aceito pra demo.

---

## 9. Ordem sugerida de port (do mais seguro pro mais invasivo)

Se quiser portar parcialmente:

1. **Bugfixes da seção 5** (TDZ, escapeHtml, script tags, etc) — todas de baixo risco, melhoram UX existente.
2. **Tests adicionais** (seção 7) — defensivos, pegam regressões.
3. **Discover Pipes** (`/api/discover-pipes`) — feature aditiva, isolada.
4. **gunicorn + Dockerfile** (seção 4) — só executa se você for fazer deploy.
5. **Tokens client-side completos** (seção 1) — refactor grande, decidir se mantém server-side ou migra.
6. **Basic Auth** (seção 2) — só ativa se setar env var.

---

## 10. Hashes de commit relevantes

Revise no histórico: `git log --oneline` na pasta demo.

- `chore: initial public demo` — baseline já com tokens client-side, basic auth, discover-pipes.
- `fix: TDZ em _onboardingShown bloqueava modal de onboarding`
- `fix: carregar v2_utils.js antes das telas V2`
- `fix: refresh do modal Gerenciar Ambientes apos onboarding`
- `fix: usar escapeHtmlInline em renderConnectedBadge`
- `feat: descoberta automatica de pipes via /api/discover-pipes`
- `fix: botao 'Criar nova configuracao cross-env' nao reagia quando lista vazia`
- `fix: scrollbar visivel em dropdowns + altura maior`

---

Última atualização: 2026-04-29 noite, durante deploy Render online.
