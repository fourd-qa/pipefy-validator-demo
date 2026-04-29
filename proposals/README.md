# Propostas de Design

Pasta livre pra dropar HTML/CSS/imagens vindas do designer e comparar visualmente com o V2 atual.

## Como organizar

Uma subpasta por iteração, com nome `YYYY-MM-DD_<labelcurta>/`:

```
proposals/
├── README.md                     ← este arquivo
├── 2026-04-26_v1/                ← iteração 1
│   ├── configuracao.html
│   ├── resultados.html
│   ├── execucao.html
│   ├── assets/
│   │   ├── style.css
│   │   └── screenshot.png
│   └── notas.md                  ← (opcional) descrição das mudanças
├── 2026-05-03_v2/                ← iteração 2
│   └── ...
```

Cada subpasta é tratada como uma iteração isolada. Não precisa estar completa, podem ser apenas mockups parciais ou imagens.

## Como acessar

A pasta é volume-mount no Docker. Reflete imediato sem rebuild:

- **Índice de iterações:** `http://localhost:8080/proposals/`
- **Arquivo direto:** `http://localhost:8080/proposals/2026-04-26_v1/configuracao.html`
- **Asset relativo:** funciona, mantém o mesmo prefixo da iteração

## Como comparar com o V2 atual

Abre 2 abas lado a lado:
- `http://localhost:8080/v2/configuracao` (V2 atual)
- `http://localhost:8080/proposals/<iteracao>/configuracao.html` (proposta)

## Convenções pro designer

Pode entregar tanto HTML quanto Figma export, screenshots ou mockups soltos. Idealmente:

- HTML autocontido (CSS inline ou em arquivo único na mesma pasta)
- Tema dark coerente com o V2 atual: navy `#0b0f1a` + ocre `#c9a84c`
- Fonte sistema (`Inter`, `-apple-system`) + mono `JetBrains Mono` pra IDs/UUIDs
- Sem framework: vanilla CSS, vanilla JS

## Workflow sugerido

1. Designer dropa arquivos numa subpasta nova
2. Eu (André) abro o índice em `/proposals/` e comparo com o V2 atual
3. Listo o que vale implementar e o que descartar
4. Implementação incremental no V2, não substituição completa
