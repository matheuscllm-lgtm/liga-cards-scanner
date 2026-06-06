# HANDOFF · Scanner Liga Pokémon (retome por aqui)

> **Para o Claude da próxima sessão:** este é o arquivo de contexto/handoff do
> projeto. É a memória da última conversa e o **ponto de retomada**. Leia ele
> primeiro, junto com o [`CLAUDE.md`](CLAUDE.md) (manual técnico do repo). O
> usuário fala **português**. Branch de trabalho: `claude/adoring-ramanujan-JnS8b`.
>
> Última atualização: **2026-06-06**.

---

## ⏯️ Onde retomar (TL;DR)

O projeto está **completo e funcional na `main`** — 106 testes passando, CI
verde, dependências enxutas. **Não há bug nem trabalho de código pendente.** O
que sobra são tarefas manuais do usuário e melhorias opcionais.

Se o usuário pedir pra continuar, quase certamente é um destes:

1. **Mergear o PR #18** (`CLAUDE.md` + este arquivo) na `main` — falta a decisão
   dele (na última sessão preferiu deixar em draft).
2. **Apagar as 14 branches órfãs** → **Issue #17** (manual; ver fim do arquivo).
3. **Arquivar** o repositório duplicado `liga-arbitrage-scanner`.
4. **Atualizar o `README.md`** (doc drift — ver seção de erros).
5. (Opcional) Montar um `data/liga_offers.csv` real e rodar o caminho de
   produção ponta-a-ponta; melhorar o matcher; coletor real da Liga.

---

## 📌 O que é o projeto

Scanner de **arbitragem de cards Pokémon**: compara o preço de oferta na **Liga
Pokémon** (marketplace BR, R$) com o preço de referência do **TCGplayer** (USD,
via API pública pokemontcg.io), converte tudo para BRL e lista cards com
**margem ≥ 25%** e **preço ≥ R$50**, ordenados por maior margem.

```
Margem% = ((TCG_BRL − Liga_BRL) / Liga_BRL) × 100
Aprovado  ⇔  preço_liga ≥ R$50  E  margem ≥ 25%
```

## 🧱 Arquitetura (resumo — detalhes no CLAUDE.md)

```
src/main.py              Pipeline: rate → ofertas Liga → refs TCG → match → reports (JSON+CSV+XLSX) → resumo
src/collectors/
  liga_pokemon.py        fetch_offers(source) → LigaOffer.  mock | csv | http(stub)
  tcgplayer.py           fetch_reference_prices(source, queries) → TCGReference.  mock | csv | pokemontcg | api(stub)
  pokemontcg.py          cliente pokemontcg.io: cache disco 24h + retry backoff; escolhe menor market price
src/matching/
  card_matcher.py        match_cards() → Comparison. exato → fuzzy difflib (nome .7/set .3, thr .85); ordena por margem
  normalization.py       lowercase, sem acento, aliases de set, VMAX/VSTAR/VUNION
src/pricing/
  currency.py            get_exchange_rate() (fixo / auto AwesomeAPI); convert_usd_to_brl()
  margin.py              calculate_margin(); is_approved(). MIN_MARGIN=25%, MIN_PRICE=R$50
src/reporting/xlsx.py    write_xlsx() — header colorido, moeda/%, tinta por status, hyperlinks
```

## ⚙️ Como rodar

```bash
pip install -r requirements.txt
pytest -q                 # 106 testes
python src/main.py        # default: tudo mock, sem internet → reports/report_<ts>.{json,csv,xlsx}

# caminho de produção (você fornece só as ofertas; preço TCG vem automático):
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

---

## ✅ O que foi feito nesta sessão

- Comparados os dois repositórios duplicados (`liga-pokemon-scanner` e
  `liga-arbitrage-scanner`); decisão de **manter só este** e consolidar tudo.
- **PR #15** — consolidou o scanner completo na `main` (antes a `main` só tinha
  o README; a implementação estava espalhada em 14 PRs draft). ✅ mergeado.
- **PR #16** — limpou o `requirements.txt` (removeu `requests`/`beautifulsoup4`/
  `lxml`, não usados; sobrou só `openpyxl`). ✅ mergeado (squash → `52f18b1`).
- **Issue #17** — aberta para rastrear a exclusão das 14 branches órfãs.
- **`CLAUDE.md`** + **`HANDOFF_SCANNER_LIGA.md`** — criados para preservar
  contexto entre sessões. Estão no **PR #18** (draft, CI verde).

## 🗣️ Decisões e pontos discutidos

- **Um repositório só:** consolidar em `liga-pokemon-scanner`, arquivar o duplicado.
- **Liga bloqueia scraping** (403) e **TCGplayer oficial exige credenciais** →
  caminho escolhido: **CSV manual** (ofertas) + **pokemontcg.io** (preço TCG,
  sem auth). Modos `http`/`api` ficam stubs.
- **Variantes:** card com várias versões no set → pega a de **menor market price**
  (assume que a Liga vende a regular).
- **Deps mínimas:** só `urllib` (stdlib) + `openpyxl`.

---

## 📦 Estado atual (git / PRs / CI)

| Item | Estado |
|---|---|
| `main` | `52f18b1` — funcional, 106 testes, CI verde |
| PR #15 | ✅ mergeado (consolidação) |
| PR #16 | ✅ mergeado (limpeza de deps) |
| PR #18 | 🟡 **draft**, CI verde (`CLAUDE.md` + `HANDOFF_SCANNER_LIGA.md`) |
| Issue #17 | 🔓 aberta (apagar 14 branches órfãs) |
| Branch de trabalho | `claude/adoring-ramanujan-JnS8b` |

---

## ⚠️ Erros conhecidos, limitações e gotchas

**Código:** **nenhum bug conhecido** — 106 testes verdes, CI verde. O scanner
roda ponta a ponta no modo mock e gera JSON + CSV + XLSX.

**Stubs propositais (não são bugs — levantam `NotImplementedError` de propósito):**
- `LIGA_OFFERS_SOURCE=http` → Liga bloqueia clientes não-browser (403); o brief
  proíbe burlar. Use `csv`.
- `LIGA_TCG_SOURCE=api` → TCGplayer oficial exige credenciais. Use `csv` ou
  `pokemontcg`.

**Limitações do ambiente remoto (atrapalharam tarefas, não o código):**
- `git push --delete` → **HTTP 403** (o proxy só libera a branch de trabalho).
  Por isso as 14 branches órfãs **não puderam ser apagadas daqui** → viraram a
  Issue #17 (manual).
- **GitHub MCP não tem** ferramenta de apagar/renomear branch (só criar/listar) —
  logo, nem deletar nem "marcar via rename" é possível do meu lado.
- `pull_request_read get_status` → **403 "Resource not accessible by integration"**
  (sem permissão pro combined status). Contornado com `get_check_runs`, que funciona.
- **`send_later` indisponível** → não dá pra agendar auto check-in do PR.

**Doc drift a corrigir no `README.md`:** as seções "Estrutura" e "Próximos
passos" estão desatualizadas (o câmbio ao vivo via `auto` **já existe**; o
diagrama de árvore não lista `pokemontcg.py`, `normalization.py`, `currency.py`,
`xlsx.py`).

---

## 🧹 Pendências e próximos passos

1. **PR #18** — mergear na `main` (pra `CLAUDE.md`/handoff carregarem sozinhos
   em sessões futuras). Aguardando decisão do usuário.
2. **Issue #17** — apagar as 14 branches órfãs (manual; comando abaixo).
3. **Arquivar** `liga-arbitrage-scanner`.
4. **Corrigir o doc drift** do `README.md`.
5. (Opcional) `liga_offers.csv` real + caminho de produção; coletor real da
   Liga (robots.txt/rate limit); integração oficial TCGplayer; melhorar matcher
   (aliases de set, nomes PT↔EN, mais variantes).

---

## 🗑️ Issue #17 — apagar 14 branches órfãs (manual)

Drafts antigos já mergeados/fechados. **Manter** `main` + a branch ativa.
Fazer pela UI do GitHub (`/branches` → 🗑️) ou, localmente, tudo de uma vez:

```bash
git push origin --delete \
  claude/ci-workflow-py311 \
  claude/install-windows-guide \
  claude/liga-csv-collector \
  claude/main-integration-tests \
  claude/normalization-matcher \
  claude/pokemon-league-scanner-sGa15 \
  claude/pokemontcg-collector \
  claude/pokemontcg-integration \
  claude/powershell-runner \
  claude/readme-modes \
  claude/robustness-improvements \
  claude/tcgplayer-csv-collector \
  claude/unit-tests \
  claude/xlsx-report
```
