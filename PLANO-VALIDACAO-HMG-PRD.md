# Plano Estratégico de Validação HMG → PRD

Documento canônico da visão estratégica de cobertura do Pipefy Validator. Foca em maximizar a captura de erros antes da promoção, com paralelos diretos com as práticas de validação de software de mercado.

Última atualização: 2026-05-01
Status atual: L3 (Validação Estrutural)
Próxima meta: L4 (Validação Semântica + Impacto)

---

## Sumário executivo

A ferramenta hoje funciona como um Terraform Plan reduzido pro Pipefy. Captura divergências estruturais visíveis (phases, fields, automations, conditions). Já é mais do que 90% das equipes fazem hoje no mercado.

Mapeando as práticas de validação de software de mercado, 25 categorias têm equivalente factivel no contexto Pipefy. Hoje cobrimos 4%. Com os dados que a API GraphQL já expõe, conseguimos chegar em 88%. Os 12% restantes são limitações da plataforma, não da ferramenta.

A recomendação é evoluir em 3 frentes priorizadas: equivalente Gitleaks/Snyk (segurança), equivalente SonarQube (qualidade), equivalente Datadog Synthetics (smoke pós promoção). Cada frente é aditiva, sem risco de quebrar o código atual.

---

## 1. Modelo de maturidade da validação

| Nível | Nome | O que valida | Onde estamos |
|-------|------|--------------|--------------|
| L1 | Reativo | Cliente descobre o bug em produção | Mercado em geral |
| L2 | Manual | QA olha cada pipe na UI antes do deploy | Pré ferramenta |
| L3 | Estrutural | Phases, fields, automations, conditions | **HOJE** |
| L4 | Semântica + impacto | Detecta intenção errada, calcula blast radius | Próximas 2 sprints |
| L5 | Dinâmica | Cria card teste pós promoção, valida fluxo real | Sprint 3 a 4 |
| L6 | Governança | Drift contínuo, alerta se PRD muda fora do processo | Roadmap longo |

A barra do L3 já é maior do que 90% das equipes. O salto pra L4 é o que vira diferencial e pega a maioria dos bugs reais que a estrutura não pega.

---

## 2. O que validamos hoje (L3)

### Estrutura via `pipe_structure.graphql`

* Phases: nome, existência
* Fields por fase + start_form: id, label, type, required, options
* Labels: nome, cor

### Automations via `automations_list.graphql`

* Status (active true/false)
* `action_id`, `event_id`
* `action_params`: `to_phase_id`, `url`, `body`, `headers`, `httpMethod`
* `event_params`: `triggerFieldIds`, `phase`, `to_phase_id`, `fromPhaseId`, `inPhaseId`
* `condition`: expressions com `field_address`, `operation`, `value`

### iPaaS via Activepieces

* Flows com status, trigger, steps

### Modos de execução

Single, Cross (HMG vs PRD), Snapshot (gerar/comparar), Batch, Health Check.

### Categorias filtráveis

Pipefy: SF (Start Form), FA (Fases e Campos), LB (Labels), AS (Auto Status), AD (Auto Fase Destino), AH (Auto HTTP), AC (Auto Condition).
iPaaS: IF (Flow), IT (Trigger), IS (Steps).

---

## 3. Mapa de cobertura por categoria de risco

| Risco real na promoção | Hoje (L3) | L4 | L5 | L6 |
|------------------------|-----------|----|----|----|
| Phase, field ou automation faltando | Sim | Sim | Sim | Sim |
| Tipo, obrigatoriedade ou opção de campo divergente | Sim | Sim | Sim | Sim |
| Conditions de automation diferentes | Parcial | Sim | Sim | Sim |
| URL de webhook apontando pro ambiente errado | Não | **Sim** | Sim | Sim |
| Tokens de teste em headers de PRD | Não | **Sim** | Sim | Sim |
| Email destinatário de teste em PRD | Não | **Sim** | Sim | Sim |
| Automation refere campo já deletado | Não | **Sim** | Sim | Sim |
| Campo removido com cards reais usando ele | Não | **Sim** | Sim | Sim |
| Phase renomeada com cards parados nela | Não | **Sim** | Sim | Sim |
| Estrutura idêntica mas fluxo quebra em runtime | Não | Não | **Sim** | Sim |
| Webhook recebe payload errado em prod | Não | Não | **Sim** | Sim |
| Ordem de phases mudou | Parcial | **Sim** | Sim | Sim |
| Cor de label, descrição de campo, help text | Não | **Sim** | Sim | Sim |
| SLA por fase, deadlines | Não | Roadmap | Roadmap | Sim |
| Permissões por papel, link público de form | Não | Roadmap | Roadmap | Sim |
| Conexão com tabela auxiliar perdida | Não | Roadmap | Roadmap | Sim |
| Email template HTML mudou silencioso | Não | Roadmap | Roadmap | Sim |
| Alguém alterou PRD direto, fora do processo | Não | Não | Não | **Sim** |
| Divergência crônica HMG vs PRD que ninguém resolve | Não | Não | Não | **Sim** |

---

## 4. Comparativo com mercado de software (top 25 categorias)

| # | Categoria | Ferramenta de mercado | Equivalente Pipefy | Status |
|---|-----------|----------------------|---------------------|--------|
| 1 | Schema diff, infra plan | Terraform plan, Liquibase | Compara estrutura HMG vs PRD | **Já fazemos** |
| 2 | Static analysis estrutural | SonarQube, Pylint | Phase órfã, automation sem destino | Dados atuais |
| 3 | Lint de naming | ESLint, ruff | Phases ou fields fora do padrão | Dados atuais |
| 4 | Type checking | TypeScript, mypy | Condition.value compatível com tipo do field | Dados atuais |
| 5 | Secret scanning | Gitleaks, TruffleHog | Tokens hardcoded em headers, body | Dados atuais |
| 6 | Security static | Bandit, Snyk Code | URL HTTP sem TLS, IP privado | Dados atuais |
| 7 | Cross reference | IDE find references, Sonar | Automation aponta pra field deletado | Dados atuais |
| 8 | Configuration drift | Terraform drift, AWS Config | Snapshot histórico, comparação contínua | Dados atuais |
| 9 | Environment hygiene | dotenv linter | URL HMG em PRD, email teste em PRD | Dados atuais |
| 10 | Documentation coverage | docstring lint | Campo sem description | Ampliando query |
| 11 | Coverage de regras | pytest cov | % de phases com automation | Ampliando query |
| 12 | Contract testing | Pact, OpenAPI | Webhook responde com schema esperado | Ampliando query |
| 13 | Integration tests E2E | Playwright, Cypress | Card teste percorre o pipe pós promoção | Ampliando query |
| 14 | Smoke tests | health endpoints | Card teste no fluxo crítico em segundos | Ampliando query |
| 15 | Performance tests | k6, JMeter | Latência média de webhook, P95 por fase | Ampliando query |
| 16 | Load tests | Locust | Stress: N cards em sequência | Ampliando query |
| 17 | Dependency scanning | Dependabot | Integrações conectadas (Drive, Slack) | Ampliando query |
| 18 | Compliance scanning | SOC2, PCI | Campo sensível marcado, audit trail | Ampliando query |
| 19 | Permission audit | AWS IAM Analyzer | Quem vê, quem edita, link público | Ampliando query |
| 20 | Blast radius | impact analyzer | Cards reais impactados antes da mudança | Ampliando query |
| 21 | Mutation testing | Stryker | Muda condition de propósito | Limitação plataforma |
| 22 | Chaos engineering | Chaos Monkey | Derrubar webhook, simular SLA | Limitação plataforma |
| 23 | Canary release | LaunchDarkly | Subir phase pra X% dos cards | Limitação plataforma |
| 24 | Observability / SLO | Datadog, Prometheus | Dashboard de execução, MTTR | Ampliando query |
| 25 | Synthetic monitoring | Datadog Synthetics | Cron que cria card teste | Ampliando query |

### Resumo executivo da cobertura

| Status | Quantidade | % |
|--------|-----------|---|
| Já cobrimos | 1 | 4% |
| Cobrimos com dados atuais (custo: só código) | 8 | 32% |
| Cobrimos ampliando query (custo: código + query) | 13 | 52% |
| Limitação real da plataforma | 3 | 12% |

**88% das categorias de validação de software de mercado têm equivalente factivel no Pipefy.**

---

## 5. Top 7 frentes priorizadas com equivalente de mercado

| # | Equivalente | Função no Pipefy | Valor | Esforço |
|---|-------------|------------------|-------|---------|
| 1 | Terraform Plan | Diff estrutural antes de aplicar | Já temos | Done |
| 2 | SonarQube | Static analysis: cross ref, dead code, naming, complexidade | Pega automation orfã, padrão fora do guideline | Baixo |
| 3 | Gitleaks + Snyk Code | Secret scanning + SAST | Token hardcoded, URL HMG em PRD, webhook sem TLS | Baixo |
| 4 | Datadog Synthetics | Smoke pós promoção, fluxo crítico em segundos | Confidence final, time promove sem medo | Médio |
| 5 | AWS Config + Terraform Drift | Detecta mudança fora do processo | Compliance, governança | Médio |
| 6 | Pact + Postman | Contract testing dos webhooks | Garante schema/payload do contrato externo | Médio |
| 7 | AWS IAM Access Analyzer | Audit de quem tem acesso a quê | Quem vê, quem edita, link público | Médio |

---

## 6. As 3 frentes recomendadas

### Frente 1: equivalente **Gitleaks + Snyk Code** (segurança)

**Pitch executivo:** "Hoje qualquer dev pode subir uma automation com URL HMG em PRD e ninguém vê. Vamos colocar o equivalente a Gitleaks. Bloqueia no momento da promoção, igual SOC2 audit pediria."

**Bugs que captura:**

| Padrão de mercado | Equivalente Pipefy |
|--------------------|---------------------|
| Token vazado em código | Token em header de automation HTTP |
| URL com query string contendo token | URL `https://api.x.com?token=abc` em automation |
| Endpoint HTTP sem TLS | URL começando com `http://` em automation de PRD |
| URL apontando pra localhost | Webhook em `192.168.*`, `10.*`, `localhost` em PRD |
| Endpoint de teste em prod | URL com `hmg.`, `staging.`, `qa.`, `test.` em PRD |
| Email de QA hardcoded em prod | Destinatário `qa@`, `+test`, domínio teste em PRD |

**Por que primeiro:** ROI mais alto, custo mais baixo, narrativa de compliance entende imediatamente. Pega o bug número 1 da promoção (URL HMG em PRD) com configuração curta.

**Implementação:** novo arquivo `config/semantic_rules.json`, nova categoria SC, nova keyword `Comparar Regras Semanticas` no `comparator.resource`, sem mexer em código existente.

### Frente 2: equivalente **SonarQube** (qualidade)

**Pitch executivo:** "Hoje fazemos Terraform Plan. Vamos adicionar o equivalente a Sonar. Vai virar dashboard de qualidade do pipe ao longo do tempo, com alerta em PR quando algo cai."

**O que captura:**

| Sonar checa | Equivalente Pipefy |
|-------------|---------------------|
| Variável declarada e nunca usada | Field criado e nenhuma automation refere |
| Função privada nunca chamada | Phase sem entrada possível |
| Import quebrado | `triggerFieldIds` aponta pra field deletado |
| Complexidade alta | Automation com 10+ conditions aninhadas |
| Naming convention violada | Phase ou field fora do padrão da empresa |
| Magic number | Condition.value com ID hardcoded |
| Unreachable code | Automation com condition que nunca pode ser verdadeira |

**Por que segundo:** dashboard que evolui ao longo do tempo. Em 3 meses temos número pra apresentar: "reduzimos automations órfãs em X%". Mostra debt acumulado.

**Implementação:** novo `resources/keywords/quality_scanner.resource`, nova categoria QS, novo arquivo `results/quality_report.json`, frontend ganha aba nova.

### Frente 3: equivalente **Datadog Synthetics** (confidence)

**Pitch executivo:** "Promover hoje é fé. Vamos adicionar o equivalente a Datadog Synthetics. Depois de toda promoção, a ferramenta cria um card teste, percorre o fluxo crítico em segundos e confirma que está funcionando."

**O que captura:**

| Datadog Synthetics faz | Equivalente Pipefy |
|------------------------|---------------------|
| Login flow em prod a cada 5min | Cria card teste no PRD a cada deploy |
| Checkout flow valida pagamento | Move card por todas as fases críticas |
| API health check com schema | Dispara automation, valida webhook recebeu payload correto |
| Métricas de latência por step | Tempo médio de cada fase, P95 de webhook |
| Alerta se passo X falha | Notifica time se card não passou da fase 3 |

**Por que terceiro:** smoke pós promoção. Time perde medo de promover sexta à tarde. Mudança cultural visível. Em 6 meses tem case pra contar.

**Implementação:** novo `tests/post_promote_smoke.robot`, queries novas pra `card_create`, `move_card`, `card_history`. Resultado em `results/smoke_validations.json`.

---

## 7. Arquitetura segura para evolução

### Princípio: tudo aditivo, zero risco de quebrar produção

Três decisões da arquitetura atual favorecem extensibilidade:

1. **Comparator modular por categoria.** Cada validação roda dentro de `IF Categoria Habilitada`. Adicionar nova categoria não muda o comportamento das 7 atuais.

2. **GraphQL queries em arquivos separados.** Cada validação nova vira arquivo `.graphql` novo. Não toca em queries existentes.

3. **Server.py com modos isolados.** Cada modo é um `elif` em `run_validation()`. Adicionar modo novo não toca nos existentes.

### Tabela de risco por tipo de adição

| Tipo de adição | Risco | Estratégia |
|----------------|-------|-----------|
| Nova categoria de validação (SC, BR, QS) | Zero | Gated por filtro, opt in |
| Nova query GraphQL em arquivo novo | Zero | Não toca em existentes |
| Novo modo no `/api/run` | Zero | `elif` novo, default cai em single |
| Nova keyword no `comparator.resource` | Zero | Roda só se chamada |
| Novo endpoint `/api/security_scan` | Zero | Rota nova, separada |
| Adicionar campo em query existente | Baixo | Cobertura de testes pega; backend usa `.get()` com default |
| Mudar comportamento de keyword existente | Médio | Evitar; preferir nova keyword |
| Mudar shape do `validations.json` | Alto | Frontend depende; usar campo novo, não substituir |

### Estratégia de implementação por frente

Para cada frente nova, mesmo padrão:

1. **Tudo opt in por feature flag** (categoria nova só roda se UI marcou)
2. **Arquivos separados sempre que possível** (resource, robot, query, output)
3. **Teste isolado por frente** (mesmo padrão dos 136 pytest atuais)
4. **Output em arquivo separado** (security_findings.json, quality_report.json, smoke_validations.json)
5. **Versionamento** (`tool_version` no metadata sobe a cada frente)

### Riscos reais a considerar

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| Performance: queries adicionais aumentam tempo de run | Média | Categorias opt in |
| Rate limit Pipefy | Baixa | Já paginamos automations |
| API Pipefy mudar shape de campo novo | Baixa | Schema canary (CT07) detecta |
| Frontend pesado com 4 abas | Média | Modular, mostra só o selecionado |
| Token vazar em log | Baixa | Esterilização do `active*.robot` cobre |

---

## 8. KPIs executivos

| Métrica | Como medir | Por que importa |
|---------|------------|-----------------|
| % de promoções validadas pela ferramenta | Logs de runs vs deploys reais | Adoção, base de qualquer outro KPI |
| Bugs encontrados antes do deploy | Runs com `DIVERGENCIAS_ENCONTRADAS` que viraram fix | Prova de valor direta |
| Tempo médio de validação | `elapsed_final` médio nos resultados | ROI vs validação manual |
| Incidentes em produção pós promoção | Cruzar com Jira, ServiceNow, ticketing | Indicador de fim, deve cair em cada nível |
| Drifts detectados sem PR (a partir do L6) | Cron de comparação contínua | Governança, valor pra compliance |
| Tempo entre promoção e detecção de bug | Antes era "o cliente conta", agora é minutos | Mostra velocidade de resposta |

---

## 9. Roadmap em fases

| Fase | Sprints | Entrega | Equivalente de mercado | Gain principal |
|------|---------|---------|------------------------|----------------|
| Done | Concluído | L3 estrutural completo | Terraform Plan reduzido | Status quo |
| Fase A | 1 a 2 | Frente 1: semantic checks + secret scan | Gitleaks + Snyk Code | Pega 80% dos bugs reais que escapam |
| Fase B | 3 a 4 | Frente 2: quality scanner | SonarQube | Dashboard de qualidade ao longo do tempo |
| Fase C | 5 a 6 | Frente 3: smoke pós promoção | Datadog Synthetics | Confidence cultural, sem medo |
| Fase D | 7 a 9 | Blast radius + áreas extras (SLA, permissões, integrações, email templates) | Terraform Plan completo + IAM Analyzer | Cobre as áreas críticas que hoje passam |
| Fase E | 10+ | Drift detection contínuo + alertas | AWS Config + Terraform Drift | Vira ferramenta de governança/compliance |

---

## 10. Decisão estratégica em aberto

Três caminhos possíveis pra próxima sprint, cada um com narrativa de produto diferente:

### Caminho 1: profundidade

Investe Fases A, B, C antes de espalhar. Vira referência interna de qualidade. Time pequeno, equipe atual.

### Caminho 2: largura

Investe Fases A e D antes de C. Cobre mais áreas do Pipefy mais rápido. Útil se cliente reclama de "isso não valida".

### Caminho 3: produto

Pula pra Fase E paralelo, transforma a ferramenta em SaaS de governança Pipefy. Requer time dedicado, virou linha de produto.

A escolha define a narrativa do roadmap, não o esforço técnico. Os 3 reaproveitam a base atual.

---

## 11. Pitch único pra defender em comitê

**Frase de fechamento:**

"Hoje a ferramenta entrega o equivalente a um Terraform Plan reduzido. Com os dados que a Pipefy já expõe via API, conseguimos chegar em 88% do que o mercado faz pra validar software antes de produção. As 12% restantes são limitações nativas da plataforma, não da nossa ferramenta. O código atual foi feito modular o suficiente pra adicionar essas frentes sem tocar no que está em produção. Cada nova validação é um arquivo novo, um endpoint novo opcional, um teste novo. Risco de regressão é protegido pelos 136 testes que rodam em CI."

---

## 12. Próximos passos sugeridos

1. **Validar este plano com stakeholders.** Confirmar nível L4 como meta da próxima sprint.
2. **Escolher caminho estratégico** (profundidade, largura ou produto) e congelar narrativa.
3. **Detalhar Frente 1** em escopo de PR: arquivos a criar, regras a configurar, KPIs a medir.
4. **Configurar dashboard de KPIs** no `web/designs/` antes de começar Frente 1, pra ter baseline.
5. **Atualizar `HANDOFF.md` seção 9 (Roadmap)** referenciando este documento como fonte canônica do plano de evolução.

---

## Apêndice A: links e referências internas

* `HANDOFF.md` — documento canônico do projeto
* `BACKUP.md` — estratégia de backup
* `CHANGELOG-DEMO.md` — histórico de mudanças
* `resources/queries/` — queries GraphQL
* `resources/keywords/comparator.resource` — lógica de comparação
* `tests/` — suítes de teste (136 pytest, 35 vitest, 15 smoke Robot, cobertura 99% em server.py)
