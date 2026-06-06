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
pytest -q                 # 106 testes
python src/main.py        # roda o scanner (default: tudo mock, sem internet)
                          # -> reports/report_<timestamp>.{json,csv,xlsx}
```

Windows: `01_setup.ps1` -> `02_scan_liga.ps1` -> `03_scan_real.ps1` (ver `INSTALL_WINDOWS.md`).

## Modos (variáveis de ambiente)

| Variável | Default | Valores |
|---|---|---|
| `LIGA_USD_BRL_RATE` | `5.20` | float / `auto` (cotação ao vivo AwesomeAPI, fallback 5.20) |
| `LIGA_OFFERS_SOURCE` | `mock` | `mock` / `csv` / `http` (stub) |
| `LIGA_OFFERS_CSV` | `data/liga_offers.csv` | path — header `card_name,set_name,price_brl,url[,condition,seller]` |
| `LIGA_TCG_SOURCE` | `mock` | `mock` / `csv` / `pokemontcg` / `api` (stub) |
| `LIGA_TCG_CSV` | `data/tcgplayer_prices.csv` | path — header `card_name,set_name,market_price_usd[,url]` |
| `LIGA_POKEMONTCG_CACHE_DIR` | `data/cache/pokemontcg` | path / vazio (desabilita cache) |

Caminho de produção (você fornece só as ofertas; o preço TCG vem automático):

```bash
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

Os CSVs reais (`liga_offers.csv`, `tcgplayer_prices.csv`) estão no `.gitignore`.

## Arquitetura

```
src/main.py              Pipeline: rate -> ofertas Liga -> refs TCG -> match -> reports (JSON+CSV+XLSX) -> resumo no stdout
src/collectors/
  liga_pokemon.py        fetch_offers(source) -> LigaOffer.  mock | csv | http(stub 403)
  tcgplayer.py           fetch_reference_prices(source, queries) -> TCGReference.  mock | csv | pokemontcg | api(stub)
  pokemontcg.py          fetch_price() — cliente pokemontcg.io: cache em disco 24h + retry backoff (1/2/4s); escolhe a variante de menor market price
src/matching/
  card_matcher.py        match_cards() -> Comparison.  exato (chave normalizada) -> fuzzy difflib (nome .7 / set .3, thr .85); ordena por margem
  normalization.py       lowercase, remove acento, aliases de set (obf -> obsidian flames...), VMAX/VSTAR/VUNION
src/pricing/
  currency.py            get_exchange_rate() (fixo / auto); convert_usd_to_brl()
  margin.py              calculate_margin(); is_approved().  MIN_MARGIN=30% (bruta, sem taxa), MIN_PRICE=R$50
src/reporting/
  xlsx.py                write_xlsx() — header colorido, formato moeda/%, tinta por status, hyperlinks, freeze panes, autofilter
```

## Convenções e gotchas

- **Dependências mínimas**: só `urllib` (stdlib) + `openpyxl`. `requests`/`beautifulsoup4`/`lxml` foram removidos por não serem usados; não readicionar sem uso real.
- **Coletores nunca abortam o pipeline por dado ruim**: pulam a linha inválida com `logger.warning` e seguem.
- **`http` (Liga) e `api` (TCGplayer) são stubs propositais** — Liga bloqueia clientes não-browser (403) e o TCGplayer oficial exige credenciais. O brief proíbe burlar bloqueios; use `csv` ou `pokemontcg`.
- **pokemontcg.io**: para cards com várias versões no mesmo set, escolhe a de **menor `market`** (assume que a Liga lista a versão regular).
- **CI** (`.github/workflows/ci.yml`): Python 3.11 -> `pytest -q` + smoke do scanner com dados mock. Dispara em push na `main` e em todo PR.

## Estado e pendências

- `main` funcional, 106 testes, CI verde. PRs #15 e #16 já mergeados.
- **Issue #17** — apagar 14 branches órfãs. É tarefa manual: o ambiente remoto bloqueia `git push --delete` (403) e o GitHub MCP não tem ferramenta de apagar/renomear branch. Manter `main` + a branch ativa.
- Arquivar o repositório duplicado `liga-arbitrage-scanner`.
- **Doc drift no `README.md`**: as seções "Estrutura" e "Próximos passos" estão desatualizadas (ex.: o câmbio ao vivo via `auto` já existe; o diagrama de árvore não lista `pokemontcg.py`, `normalization.py`, `currency.py`, `xlsx.py`).

---

## 📤 Entrega de resultados — tabela na plataforma, NUNCA arquivo

**Regra dura (operador, 2026-06-06). Vale para TODOS os scanners (CardTrader / MYP / Liga / sealed / PSA).**

O resultado de um scan é entregue ao operador **como tabela no chat do Claude Code** — no **terminal ou no app**. **NÃO** entregar como arquivo `.xlsx`/`.csv` para download por padrão.

- O scanner/postprocess **pode escrever** uma planilha local como subproduto de trabalho (gitignored) — tudo bem. O ponto é a **ENTREGA**: ela é a tabela na plataforma, não um anexo de arquivo.
- Gerar/anexar arquivo **só quando o operador pedir explicitamente** (ex.: "me manda o XLSX pra importar em lote"). Sem pedido = sem arquivo.
- A tabela traz **todos** os deals (não amostra curada) + as colunas relevantes da fonte.
