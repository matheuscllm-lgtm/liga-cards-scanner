---
name: scan-liga
description: >-
  Rodar o scan de arbitragem da Liga Pokémon (coleta de ofertas + comparação
  com o preço de referência do TCGplayer) e ENTREGAR o resultado no formato
  padrão da frota (formato MYP). Use SEMPRE que for escanear a Liga, comparar
  preços Liga vs TCG, ou entregar/reapresentar o resultado de um scan deste
  repo — o procedimento de execução e o formato de entrega são obrigatórios
  e não mudam de sessão pra sessão.
---

# Scan da Liga Pokémon — procedimento único + entrega no formato MYP

Este skill existe para que **todo scan da Liga rode do MESMO jeito e a entrega
saia SEMPRE no MESMO formato** (o padrão da frota, espelho do `myp_summary.py`
do repo myp-arbitrage-scanner). Não improvise fora deste roteiro.

## 1. Como rodar (caminho único)

Escolha o modo pela situação — os comandos são estes, literais:

```bash
# A) SCAN AO VIVO (máquina LOCAL, navegador headful — coleta + relatório):
python src/collect_liga_live.py --sets PRE            # 1 set
python src/collect_liga_live.py --sets PRE SSP JTG    # vários sets
python src/collect_liga_live.py --sets PRE --resume   # retoma scan que caiu

# B) A partir de um CSV de ofertas JÁ COLETADO (preço TCG real automático):
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py

# C) Mock/verificação (offline, sem internet — só pra testar o pipeline):
python src/main.py
```

- No Windows use `.venv\Scripts\python.exe` no lugar de `python`.
- **Sessão na nuvem/container:** a coleta ao vivo (A) é IMPOSSÍVEL — exige
  Chrome headful local (headless é barrado pelo Cloudflare). Na nuvem só
  valem os modos B (com CSV real) e C (mock). Não tente burlar o bloqueio.
- Ambos os caminhos imprimem a tabela de entrega no fim, sozinhos.

## 2. Entrega (OBRIGATÓRIA — não negociável)

- A entrega é a tabela markdown que o pipeline imprime no fim
  (`src/reporting/markdown.py::build_markdown`). **Cole-a VERBATIM no chat.**
- **PROIBIDO** montar/reformatar tabela à mão, renomear/reordenar colunas,
  dropar um link "pra economizar largura", ou transcrever números do
  CSV/JSON/XLSX. Se a tabela que você vai colar não saiu do `build_markdown`,
  pare e gere por ele.
- **NUNCA** entregar arquivo (`.xlsx`/`.csv`) por padrão — só se o operador
  pedir explicitamente.
- Formato (padrão MYP, 3 buckets — todos com `[oferta](url) · [TCG](url)`
  em TODA linha):
  - 🟢 **Aprovados (match exato)** —
    `| # | Margem % | Liga R$ | TCG US$ | Dif | Carta | Set | Raridade | Cond | Qtd | Links |`
  - ⚠️ **Aprovados com match fuzzy (validar manualmente)** — mesmas colunas
    + `Match` (score)
  - ❌ **Reprovados** (margem < mínima ou preço < piso) — mesmas colunas +
    `Match`; garante que TODAS as linhas comparadas aparecem (nunca amostra
    curada)

## 3. Regras invioláveis (frota)

- **Threshold `30` INTEIRO** (30 = 30%) — convenção MYP/Liga/eBay, OPOSTA à
  do CardTrader/COMC/Selados (que usam fração `0.30`). Não confundir.
- **Só Near Mint** — condição por match EXATO `== "NM"`, nunca substring.
- **Margem BRUTA** — `(TCG_BRL − Liga_BRL) / Liga_BRL`, sem nenhuma taxa
  embutida; frete/câmbio/IOF o operador calcula por fora.
- **Nunca inventar preço** — fonte falhou → linha pulada/rotulada, jamais
  fabricar número.
- **Sem recomendação de compra** — reporte margem, flags e fontes; a decisão
  de capital é do operador. Não existe coluna "COMPRAR".

## 4. Piso de preço — SÓ para cartas

- O piso de **R$50** é filtro de relevância que vale **apenas para cartas
  avulsas (singles)**.
- **Produtos selados (ETB, booster box, bundle, tin etc.) NÃO têm piso de
  preço.** Selados nem são escopo deste scanner — a Liga aqui é
  singles-only; selados moram no repo `sealed-scanner`. Se algum dia este
  scanner cobrir selados, o piso NÃO se aplica a eles.

## 5. Gotchas conhecidos (não redescobrir)

- Headless é barrado pelo Cloudflare — a coleta ao vivo é headful e a
  janela do Chrome não pode ser fechada durante o scan.
- O filtro "Inglês" na página da carta é OBRIGATÓRIO (checkbox
  `input#field_5_1`) — sem ele, carta dominada por PT não mostra nenhum EN.
- O preço nas linhas AJAX é anti-scraping (sprites de dígito); a decodificação
  é por template matching. Dígito que não decodifica → carta pulada com
  aviso, preço NUNCA inventado.
