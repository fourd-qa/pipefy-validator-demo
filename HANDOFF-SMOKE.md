# Handoff — Smoke Test (Fase C do L4)

Documento canônico da Frente 3 do `PLANO-VALIDACAO-HMG-PRD.md`: equivalente Datadog Synthetics aplicado a pipes Pipefy.

Última atualização: 2026-05-15.

---

## TL;DR

- **O que é**: cria card de teste no Pipefy, move pelas phases críticas, deleta no final. Valida que o fluxo real funciona, não só que a estrutura está correta.
- **Diferença das Fases A/B**: Smoke **escreve no Pipefy** (createCard, moveCardToPhase, deleteCard). Por isso tem gates fortes.
- **Onde está**: card "Smoke Test" em `/v2/dashboard`, endpoints `/api/smoke/dry-run`, `/api/smoke/run`, `/api/smoke/last`, `/api/smoke/history`, `/api/smoke/rules`, webhook listener `/api/smoke/webhook/<pipe_id>`. Engine em `smoke_runner.py`. Config em `config/smoke_rules.json`. Histórico em `results/smoke_runs/<pipe>/<ts>.json`.
- **Estado default**: **dry-run** (só simula, não chama Pipefy). Execução real é opt-in com múltiplos gates.
- **Login**: restrito a `lideranca`.
- **Testes**: 30 pytest verdes (`tests/python/test_smoke_runner.py`).

---

## 1. Como funciona

```
Cron coleta snapshot do pipe (Fase A pendência 1).
        ↓
Lideranca abre /v2/dashboard → card "Smoke Test" → escolhe pipe.
        ↓
Clica "Rodar dry-run" → /api/smoke/run com dry_run=true (default)
   → simulate_smoke retorna plano de steps sem chamar Pipefy.
        ↓
Card mostra steps simulados (create + N moves + delete).
        ↓
[OPCIONAL] Lideranca clica "Rodar execução real" → confirma diálogo
   → /api/smoke/run com dry_run=false.
        ↓
Backend valida gates: pipe enabled? token? PRD allow_prd?
        ↓
Se passa: chama _pipefy_create_card → loop _pipefy_move_card →
   _pipefy_delete_card. Captura webhook hits pelo /api/smoke/webhook/<pipe_id>.
        ↓
Persiste em results/smoke_runs/. Card recarrega via /api/smoke/last.
```

## 2. Gates de segurança

Pra `dry_run=false` chamar Pipefy, **todos** abaixo precisam estar true:

| Gate | Onde | Bloqueio retorna |
|---|---|---|
| Pipe habilitado | `config/smoke_rules.json` → `pipes[pipe_id].enabled = true` | 403 |
| Token de escrita configurado | env Render `SMOKE_PIPEFY_TOKEN` | 503 |
| Pra pipe **PRD**: allow_prd em ambos | `pipes[pipe_id].allow_prd = true` E env `SMOKE_ALLOW_PRD=true` | 403 |

Dry-run **não tem nenhum gate** — sempre funciona. Útil pra validar plano antes de executar.

Mesmo após execução real, **deleteCard sempre tenta rodar no final** (cleanup defensivo), mesmo se algum `moveCardToPhase` falhou. Se o delete falhar, fica no log um alerta `CARD ORFAO id=...` pra cleanup manual.

## 3. Passo a passo pra ativar execução real

> **Você nunca fez isso? Sem problema.** Cada passo abaixo é independente e reversível. Comece pelo pipe HMG, nunca PRD direto.

### Passo 1 — Crie (ou escolha) um pipe HMG dedicado pra smoke

Idealmente: um pipe novo no seu workspace Pipefy chamado tipo "Smoke Test HMG", com 3-4 phases ("Triagem", "Análise", "Aprovação", "Concluído") e 1-2 fields no start form.

Se preferir usar um pipe existente, escolha um **que não tem dados de cliente real**. Cards criados pelo smoke vão ter prefixo `[SMOKE-TEST]` no título — fácil de filtrar e deletar manualmente caso algo bugue.

**Anote o UUID do pipe** (vai usar nos passos 4 e 5). Pra encontrar: abre o pipe no Pipefy → URL tem o ID após `/pipes/`.

### Passo 2 — Gere um token Pipefy com escrita

1. Vai em https://app.pipefy.com/tokens (logado).
2. Clica "Generate new token".
3. Dá um nome tipo "smoke-runner-write".
4. **Não compartilhe esse token**: ele tem permissão de criar/deletar cards.
5. Copia o valor (começa com algo tipo `eyJhbGc...`). **Você só consegue ver UMA vez.** Cole num lugar seguro temporariamente (não comite).

### Passo 3 — (Opcional) Configure webhook no pipe pra capturar callbacks

Útil pra validar que automations do pipe dispararam quando o smoke move o card. Sem isso, smoke ainda funciona — só não consegue confirmar callbacks.

1. Abre o pipe no Pipefy.
2. Vai em **Configurações** → **Webhooks** (ou "Integrações").
3. Clica "Adicionar webhook".
4. URL: `https://pipefy-validator-demo.onrender.com/api/smoke/webhook/SEU_PIPE_UUID_AQUI`
   - Troca `SEU_PIPE_UUID_AQUI` pelo UUID do passo 1.
5. Eventos: marca `card.create`, `card.move`, `card.delete`.
6. Salva.

> Se o seu pipe é HMG dedicado pra smoke, deixa esse webhook ligado pra sempre. Não tem como vazar dado de cliente porque o pipe só recebe cards `[SMOKE-TEST]`.

### Passo 4 — Adicione env vars no Render

1. Vai em https://dashboard.render.com → seu serviço `pipefy-validator-demo`.
2. **Environment** (menu lateral) → **Add Environment Variable**.
3. Adiciona:
   - `SMOKE_PIPEFY_TOKEN` = valor do token do passo 2.
   - (Opcional) `SMOKE_PIPEFY_BASE_URL` = `https://api.pipefy.com/graphql` (default).
4. Salva. Render vai redeployar automaticamente (~1-2 min).

> Pra rodar smoke em pipe PRD (não recomendo no começo), também adicione `SMOKE_ALLOW_PRD=true`. Mantenha PRD desabilitado até confiar 100% no fluxo.

### Passo 5 — Edite `config/smoke_rules.json` no repo

Abre o arquivo (na raiz do projeto) e adiciona seu pipe:

```json
{
  "version": "1.0",
  "default_card_name_prefix": "[SMOKE-TEST]",
  "default_phases_match": "^(Triagem|An[áa]lise|Aprova[çc][ãa]o|Conclu[íi]do|Documenta)",
  "allow_prd_global": false,
  "pipes": {
    "SEU_PIPE_UUID_AQUI": {
      "enabled": true,
      "phases_to_cover": ["Triagem", "Análise", "Aprovação"],
      "start_form_values": {
        "field_id_do_titulo": "Cliente smoke test",
        "outro_field_id": "valor padrao"
      }
    }
  }
}
```

- **`phases_to_cover`**: lista exata dos nomes de phase pelos quais o card vai passar (ordem importa).
- **`start_form_values`**: dict de `field_id → valor`. Pra descobrir os field_ids, abre `/api/dashboard/auto-snapshots/SEU_UUID` no navegador (logado como lideranca), olha `data.pipe.start_form_fields[*].id`.

Commita e pusha:
```powershell
git add config/smoke_rules.json
git commit -m "chore: habilita smoke pra pipe HMG XYZ"
git push origin main
```

Render redeploya (~1-2 min).

### Passo 6 — Teste com dry-run primeiro

1. Abre `https://pipefy-validator-demo.onrender.com/v2/dashboard` (login `lideranca`).
2. Card "🚀 Smoke Test" no final da página.
3. Escolhe o pipe no selector.
4. Clica **"Rodar dry-run"**.
5. Card mostra os steps simulados. Confere se:
   - Phases listadas batem com o que você configurou.
   - Card name começa com `[SMOKE-TEST]`.
   - Nenhum warning.

### Passo 7 — Execute de verdade

1. Mesmo card, agora o botão **"Rodar execução real"** apareceu (verde + vermelho).
2. Clica. Aparece um confirm: "Vai criar card de teste de verdade no Pipefy...". Confirma.
3. Card mostra steps reais com tempos em ms.
4. Abre o pipe no Pipefy: vai aparecer 1 card `[SMOKE-TEST] YYYYMMDD-HHMMSS` por um momento, e ele vai sumir quando o delete rodar.
5. Se tudo OK: status "OK" verde. Se algo falhou, vai ter `❌ FALHOU` com a mensagem do erro.

### Cleanup manual (se algo der errado)

Se o smoke falhar no delete e deixar card órfão:
1. Abre o pipe no Pipefy.
2. Filtra cards por nome `[SMOKE-TEST]`.
3. Deleta manualmente.

## 4. Endpoints

| Endpoint | Auth | O que faz |
|---|---|---|
| `POST /api/smoke/dry-run` | lideranca | Simula sem chamar Pipefy. Body: `{pipe_id}`. Sempre seguro. |
| `POST /api/smoke/run` | lideranca | Body `{pipe_id, dry_run? = true}`. Com `dry_run=false` aplica todos os gates. |
| `POST /api/smoke/webhook/<pipe_id>` | público | Pipefy envia POST aqui. Captura hits em memória. |
| `GET /api/smoke/last?pipe_id=...` | lideranca | Última run pro card do dashboard. |
| `GET /api/smoke/history?pipe_id=...&limit=10` | lideranca | Histórico persistido. |
| `GET /api/smoke/rules` | lideranca | Config sumarizada + flags de token/allow_prd. |

## 5. Pendências e próximos passos

### Pendência 1: trend de smoke
`/api/smoke/history` já lista runs persistidas. Falta computar trend (success rate, latência média, regressões). Padrão pode reusar `compute_security_trend` / `compute_quality_trend`.

### Pendência 2: cron de smoke
Hoje smoke é manual (botão no dashboard). Próximo nível: GitHub Actions cron rodando dry-run diário (e talvez execução real semanal em HMG) com alertas em email se falhar.

### Pendência 3: validação de webhook hits no resultado
Hits são capturados em memória mas o resultado da run não compara "esperado vs recebido". UI mostra `hits.length`, mas não valida que todos os eventos esperados chegaram. Próximo polish: config aceita `expected_webhook_events: ["card.move:Análise", ...]` e o resultado marca quais bateram.

### Pendência 4: UI standalone `/v2/smoke`
Card no dashboard cobre o caso comum. Pra investigar profundo (ver histórico completo de runs, comparar 2 runs, etc), seria útil tela dedicada.

### Próximos níveis do plano L4
- **Fase D**: SLAs por fase, permissões, integrações, email templates
- **Fase E**: drift detection contínuo

## 6. Riscos e mitigações

| Risco | Status | Mitigação |
|---|---|---|
| Smoke roda em pipe de cliente real | Mitigado | Whitelist explícita (`enabled: true` por pipe). Pipe PRD bloqueado duplamente. |
| Card de teste vaza em prod | Mitigado | Prefixo `[SMOKE-TEST]` no título; delete sempre tenta no final. Cleanup manual documentado. |
| Token write vaza | Mitigado | Env var no Render (não vai em log, não vai em response). Pode ser revogado a qualquer momento no Pipefy. |
| moveCardToPhase falha mas delete sucede | Aceito | Run marca `ok=false` com erros específicos por step. Sem rollback automático — Pipefy não tem transação. |
| moveCardToPhase + delete falham → card órfão | Aceito + monitorado | Cleanup manual (passo 7 acima). Run record marca o `card_id` pra facilitar achar. |
| Webhook listener é público sem auth | Aceito | URL contém pipe_id (mínima obscuridade). Hit não autoriza ação — só conta. Vale ativar só pra pipe HMG dedicado ao smoke. |
| Snapshot do pipe está desatualizado | Possível | Cron coleta a cada 30min em horário comercial. Se phases mudaram recente, dry-run mostra warning de "Phase X não existe no snapshot". |
