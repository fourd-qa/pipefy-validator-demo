# Design Mocks

Pasta de mockups e iteracoes visuais usados como referencia antes de integrar ao `web/index.html` real.

Nada aqui e servido pelo Flask diretamente. Sao arquivos de referencia.

## Convencao de nomes

- `tela_resultados_v1.html`, `tela_resultados_v2.html`
- `tela_config_v1.html`
- `tela_execucao_v1.html`

Cada versao fica imutavel. Se pedir uma revisao, salva como `_v2.html`, nao sobrescreve.

## Fluxo

1. Gera ou recebe mock visual
2. Salva HTML aqui
3. Abre localmente no navegador (double click) pra validar visual
4. Quando aprovar, migra pro `web/index.html` e integra com `/api/*`
