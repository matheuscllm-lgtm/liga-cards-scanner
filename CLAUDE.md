# CLAUDE.md

Orientação para o Claude Code (e outros agentes) ao trabalhar neste repositório.

> 🔄 **Retomando uma conversa?** Leia primeiro [`HANDOFF_SCANNER_LIGA.md`](HANDOFF_SCANNER_LIGA.md) —
> a memória da última sessão e exatamente onde retomar.

## Repository purpose

Scanner de **arbitragem de cards Pokémon**. Compara o preço de oferta na **Liga
Pokémon** (marketplace BR, em R$) com o preço de referência do **TCGplayer**
(USD, obtido via API pública pokemontcg.io), converte tudo para BRL e lista os
cards com **margem bruta ≥ 30%** e **preço ≥ R$50**, ordenados por maior margem.

```
Margem% = ((TCG_BRL − Liga_BRL) / Liga_BRL) × 100   (margem BRUTA, sem taxas)
Aprovado  ⇔  preço_liga ≥ R$50  E  margem ≥ 30%
```

> **Margem é BRUTA**: só a diferença de preço entre os dois produtos. O scanner
> NÃO embute frete, taxa de cartão, IOF nem qualquer outra taxa — o operador
> calcula isso por fora, manualmente. O piso de R$50 é filtro de relevância
> (não é taxa). Regra cross-scanner do operador (2026-06-06): 30% bruta, todos
> os scanners de TCG.

## Comandos

```bash
pip install -r requirements.txt
pytest -q                 # 158 testes
python src/main.py        # roda o scanner (default: tudo mock, sem internet)
                          # -> reports/report_<timestamp>.{json,csv,xlsx}

# SCAN AO VIVO (coleta o site de verdade + relatório completo, um comando):
python src/collect_liga_live.py --sets PRE          # 1 set
python src/collect_liga_live.py --sets PRE SSP JTG  # vários sets
python src/collect_liga_live.py --sets PRE --resume # retoma scan que caiu
```

Windows: `01_setup.ps1` -> `02_scan_liga.ps1` -> `03_scan_real.ps1` (ver `INSTALL_WINDOWS.md`).

## Coletor ao vivo (src/collectors/liga_live.py)

A Liga bloqueia clientes não-browser (403/Cloudflare). O coletor ao vivo
usa **patchright + Google Chrome HEADFUL** (janela visível — headless é
barrado pelo Cloudflare). Pontos-chave:

- **Perfil próprio e isolado**: `~/.pw_profile_liga_singles` — não briga
  com o Chrome do dia a dia nem com outros scanners headful (COMC, sealed).
- **NM-only é invariante dura**: condição lida da célula dedicada
  (`div.quality` com classe `quality_nm`) com match EXATO `== "NM"`.
  NUNCA substring na linha (já vazou SP no passado).
- **EN estrito**: `div.lang img[title] == "Inglês"` — combo "Português /
  Inglês" NÃO conta.
- **Filtro "Inglês" é OBRIGATÓRIO** (armadilha nº 1, descoberta no smoke
  2026-06-10): a página da carta só carrega ~16 vendedores no load
  inicial, ordenados por preço — em carta dominada por PT, NENHUM EN
  aparece. O coletor clica o checkbox `input#field_5_1` pra o site
  carregar as ofertas EN via AJAX.
- **Preço anti-scraping** (armadilha nº 2): as linhas carregadas via AJAX
  NÃO têm o preço como texto — cada dígito é um `<div>` com classe
  ofuscada apontando pra um sprite JPG. O coletor decodifica por template
  matching (pillow+numpy, templates em `data/liga_digit_templates/`,
  herdados do scanner de selados; ground truth validado por screenshot).
  Se um dígito não decodificar, a carta é pulada com aviso
  (`preco_nao_decodificado`) — preço NUNCA é inventado.
- **"Extra: Foil" NÃO exclui**: em carta chase (SIR/secret) todos os
  vendedores marcam Foil (a carta só existe em foil). O lado TCG já casa a
  versão certa (busca por número + prioridade holofoil).
- **Pré-filtro do piso**: a listagem mostra a faixa de preço de cada carta
  (`avgp-minprc`/`avgp-maxprc`); se o máximo < R$50 a página da carta nem
  é visitada.
- **Infinite scroll** (listagem e vendedores): rola até a contagem de
  elementos estabilizar por 3 rodadas.
- **Recycle**: o Chrome é fechado/reaberto a cada ~40 páginas de carta
  (sessões longas degradam — lição do protótipo).
- **Checkpoint**: progresso em `data/liga_live_state.json`; `--resume`
  continua de onde parou.
- **Coletor honesto**: bloqueio/DOM mudado → salva HTML+screenshot em
  `data/debug/` e levanta `LigaBlockedError`/`LigaDomChangedError`.
  NUNCA inventa preço.

## Modos (variáveis de ambiente)

| Variável | Default | Valores |
|---|---|---|
| `LIGA_USD_BRL_RATE` | `5.20` | float / `auto` (cotação ao vivo AwesomeAPI, fallback 5.20) |
| `LIGA_OFFERS_SOURCE` | `mock` | `mock` / `csv` / `live` (coleta ao vivo) / `http` (stub) |
| `LIGA_OFFERS_CSV` | `data/liga_offers.csv` | path — header `card_name,set_name,price_brl,url[,condition,seller,card_number]` |
| `LIGA_SETS` | — | códigos de set p/ `live` via env (ex. `PRE,SSP`); a CLI `collect_liga_live.py` é o caminho preferido |
| `LIGA_TCG_SOURCE` | `mock` | `mock` / `csv` / `pokemontcg` / `api` (stub) |
| `LIGA_TCG_CSV` | `data/tcgplayer_prices.csv` | path — header `card_name,set_name,market_price_usd[,url]` |
| `LIGA_POKEMONTCG_CACHE_DIR` | `data/cache/pokemontcg` | path / vazio (desabilita cache) |

Caminho de produção manual (você fornece só as ofertas; o preço TCG vem automático):

```bash
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

O scanner integrado (`C:\Users\mathe\integrated-scanner`) consome exatamente
esse caminho: ele roda `src/main.py` com `LIGA_OFFERS_SOURCE=csv` se existir
`data/liga_offers.csv` real — que é o arquivo que `collect_liga_live.py`
gera. Fluxo: coletar ao vivo aqui → integrado lê sozinho.

Os CSVs reais (`liga_offers.csv`, `tcgplayer_prices.csv`) estão no `.gitignore`.

## Arquitetura

```
src/main.py              Pipeline: rate -> ofertas Liga -> refs TCG -> match -> reports (JSON+CSV+XLSX) -> resumo no stdout
src/collect_liga_live.py CLI do scan ao vivo: coleta -> data/liga_offers.csv -> relatório completo
src/collectors/
  liga_pokemon.py        fetch_offers(source) -> LigaOffer.  mock | csv | live | http(stub 403)
  liga_live.py           coletor AO VIVO (patchright + Chrome headful): parsers puros + sessão com recycle + checkpoint
  tcgplayer.py           fetch_reference_prices(source, queries) -> TCGReference.  mock | csv | pokemontcg | api(stub)
  pokemontcg.py          fetch_price() — cliente pokemontcg.io: cache em disco 24h + retry backoff (1/2/4s); escolhe a variante de menor market price
src/matching/
  card_matcher.py        match_cards() -> Comparison.  exato por número -> exato (chave normalizada) -> fuzzy difflib (nome .7 / set .3, thr .85); ordena por margem. Comparison carrega card_number (p/ a coluna Carta) + match_score (fuzzy => "validar manualmente")
  normalization.py       lowercase, remove acento, aliases de set (obf -> obsidian flames...), VMAX/VSTAR/VUNION
src/pricing/
  currency.py            get_exchange_rate() (fixo / auto); convert_usd_to_brl()
  margin.py              calculate_margin(); is_approved().  MIN_MARGIN=30% (bruta, sem taxa), MIN_PRICE=R$50
src/reporting/
  markdown.py            build_markdown() — a ENTREGA canonica (tabela markdown c/ links clicaveis). main.py imprime isto no fim.
  xlsx.py                write_xlsx() — header colorido, formato moeda/%, tinta por status, hyperlinks, freeze panes, autofilter (subproduto local)
```

## Convenções e gotchas

- **Dependências mínimas**: só `urllib` (stdlib) + `openpyxl`. `requests`/`beautifulsoup4`/`lxml` foram removidos por não serem usados; não readicionar sem uso real.
- **Coletores nunca abortam o pipeline por dado ruim**: pulam a linha inválida com `logger.warning` e seguem.
- **`http` (Liga) e `api` (TCGplayer) são stubs propositais** — Liga bloqueia clientes não-browser (403) e o TCGplayer oficial exige credenciais. O brief proíbe burlar bloqueios; use `csv` ou `pokemontcg`.
- **pokemontcg.io**: para cards com várias versões no mesmo set, escolhe a de **menor `market`** (assume que a Liga lista a versão regular).
- **CI** (`.github/workflows/ci.yml`): Python 3.11 -> `pytest -q` + smoke do scanner com dados mock. Dispara em push na `main` e em todo PR.

## Estado e pendências

- **Entrega canônica em tabela markdown (2026-06-17)**: `src/reporting/markdown.py`
  (`build_markdown`) virou a saída de entrega; `main.py` o imprime no fim de
  todo scan (substituiu a tabela de texto fixo). `Comparison` agora carrega
  `card_number` (coluna Carta = nome + número) e a célula de Links é clicável
  (`[oferta](url) · [referência de preço](url)`). Match fuzzy → nota
  "validar manualmente". 158 testes (10 novos em `tests/test_markdown.py`).
- `main` funcional, 106 testes, CI verde. PRs #15 e #16 já mergeados.
- **Issue #17** — apagar 14 branches órfãs. É tarefa manual: o ambiente remoto bloqueia `git push --delete` (403) e o GitHub MCP não tem ferramenta de apagar/renomear branch. Manter `main` + a branch ativa.
- Arquivar o repositório duplicado `liga-arbitrage-scanner`.
- **Doc drift no `README.md`**: as seções "Estrutura" e "Próximos passos" estão desatualizadas (ex.: o câmbio ao vivo via `auto` já existe; o diagrama de árvore não lista `pokemontcg.py`, `normalization.py`, `currency.py`, `xlsx.py`).

---

## 📤 Entrega de resultados — tabela markdown no chat, NUNCA arquivo (MANDATÓRIO)

**Regra dura (operador, 2026-06-06). Vale para TODOS os scanners (CardTrader / MYP / Liga / sealed / PSA).**

O resultado de um scan é entregue ao operador **como tabela markdown no chat do Claude Code** — no **terminal ou no app**. **NÃO** entregar como arquivo `.xlsx`/`.csv` para download por padrão.

### A entrega é SEMPRE gerada pela ferramenta do repo — nunca montada à mão

A tabela de entrega é produzida por **`src/reporting/markdown.py` (`build_markdown`)**, que o `src/main.py` imprime automaticamente no fim de todo scan. **NÃO** transcrever números do CSV/JSON/XLSX para uma tabela escrita na mão — isso introduz erro e perde colunas. Sempre rode o pipeline e copie a tabela que ele imprime:

```bash
# scan ao vivo (coleta + relatório + imprime a tabela markdown):
python src/collect_liga_live.py --sets PRE

# a partir de um CSV de ofertas já coletado (imprime a mesma tabela):
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

(No Windows use `.venv\Scripts\python.exe`. Esses comandos foram verificados nesta sessão — `python src/main.py` em modo mock também imprime a tabela.)

### Colunas canônicas da tabela (o que `build_markdown` emite)

`Carta | Set | Liga R$ | Ref TCG R$ | Ref TCG US$ | Margem % | Status | Links | Nota`

- **Carta** = nome **+ número** do card (ex. `Umbreon ex #161`). O número vem de `Comparison.card_number` (preenchido pelo matcher a partir da oferta Liga ou da ref TCG); sem número, só o nome.
- **Links** = `[oferta](url) · [referência de preço](url)` — **clicáveis e verificáveis**, SEMPRE os dois lados (a oferta na Liga e a referência de preço no TCGplayer).
- **Nota** = deals com match fuzzy (`match_score < 1.0`) saem marcados **`validar manualmente`** — o operador confere a versão exata da carta antes de decidir.
- Mostra **TODOS** os deals comparados (aprovados **e** rejeitados), ordenados por margem — não é amostra curada.

### Arquivo só sob pedido explícito

- O scanner **pode escrever** `reports/report_*.{json,csv,xlsx}` como subproduto local (gitignorado/efêmero) — tudo bem. O ponto é a **ENTREGA**: ela é a tabela markdown no chat, não um anexo.
- Gerar/anexar arquivo (`SendUserFile`) **só quando o operador pedir explicitamente** (ex.: "me manda o XLSX pra importar em lote"). Sem pedido = sem arquivo.
