> **Regra vigente de entrega:** [DELIVERY_CHAT.md](DELIVERY_CHAT.md). Resultados somente no chat, referência clicável e coleta nova por solicitação; substitui orientações antigas de entrega via GitHub ou preços reutilizados.

# CLAUDE.md — liga-cards-scanner

Scanner de **arbitragem de cards Pokémon (singles)**: compara o preço de oferta
na **Liga Pokémon** (marketplace BR, em R$) com o preço de referência do
**TCGplayer** (USD, via API pública pokemontcg.io) e lista os cards com margem
bruta ≥ 30% e preço ≥ R$50. Orientação para qualquer sessão Claude Code
(local ou nuvem) que trabalhe neste repositório.

> 🔄 **Retomando uma conversa?** As notas de handoff/sessão são mantidas
> **localmente** (fora do repositório, por higiene de release público). Este
> `CLAUDE.md` é o manual técnico canônico do repo.

> 🗂️ **Nomes:** o repo no GitHub chama-se **`liga-cards-scanner`**
> (org `matheuscllm-lgtm`); a pasta local no **PC do operador** é
> **`C:\Users\mathe\liga-pokemon-scanner`**. É o mesmo projeto.

## Sobre a Eli

Preferências de interação da operadora (destino do balde 1 do `/reflect`; uma
linha por preferência, no imperativo, com data/fonte). Regra de negócio NÃO
fica aqui — vai em `## Decisões`.

- **Resposta concisa, com o porquê de cada decisão e exemplo prático/real** —
  não narrar opções que não vai seguir. (preferência declarada no perfil,
  2026-09-12)
- **Pendência vai pra lista "Pendências vivas" deste `CLAUDE.md`**, não pra
  issue — o repo tem issues DESABILITADAS (a API responde 410). (pedido de
  2026-09-12)

## 🛰️ Convenções da frota (cross-scanner)

> **Manual completo** (repo privado): https://github.com/matheuscllm-lgtm/scanners-commons — erros comuns, referências de preço, chaves, GitHub Actions e modelo de entrega de TODOS os scanners. Cópia-mestra local (PC do operador): `C:\Users\mathe\scanners-commons\`.

Invariantes que valem para TODOS os scanners:

- **Margem BRUTA, mínimo 30%** — só `(revenda − compra)/compra`, sem nenhuma taxa embutida (frete, cartão, IOF — o operador calcula por fora).
- **Piso de relevância R$50 (~US$10) — SÓ para cartas avulsas (singles).** Produtos SELADOS não têm piso (decisão do operador, 2026-06-27); lá o único critério é a margem ≥30%.
- **Só Near Mint** — condição por match EXATO `== "NM"`, nunca substring (já vazou SP).
- **Nunca inventar preço** — fonte falhou → marca fallback/erro e segue; jamais fabrica número.
- **Nunca recomendar compra** — o scanner reporta margem, flags e fontes; a decisão de capital é do operador.
- **Entrega = tabela markdown no chat** (nunca XLSX/CSV por padrão), gerada pela ferramenta do repo — nunca montada à mão —, mostrando TODAS as linhas (aprovadas + rejeitadas). Coluna `Carta` = nome + número; coluna `Links` combinada = `[oferta](url) · [TCG/referência](url)`.
- ⚠️ **Convenção de threshold:** percentual inteiro (`30`) = MYP, Liga, eBay; fração (`0.30`) = CardTrader, COMC, Selados.

Erros recorrentes (3 famílias — detalhe no manual):

1. **Segredo/ambiente:** BOM/zero-width numa chave → crash latin-1 no header → scan "verde mas vazio". Setar sem BOM (`printf '%s' 'KEY' | gh secret set`) **e** sanitizar ao ler no código (`.strip()` NÃO tira BOM).
2. **Git:** branch ou `main` local defasado por squash-merge PARECE pendência. O teste real de "já mergeado" é `git diff --stat origin/main <branch>` estar vazio (não `git merge-base`).
3. **Honestidade de preço:** inflação de referência, fallback tratado como real, NM frouxo → sempre validar versão/condição e rotular fallback.

**Este scanner:** referência de preço = pokemontcg.io (**usa `POKEMONTCG_API_KEY` quando presente**; pega o menor `market` entre as variantes; cache 24h em disco) — é a **única fonte real de preço implementada** neste repo (`LIGA_TCG_SOURCE`: mock | csv | pokemontcg | api-stub); chaves = `POKEMONTCG_API_KEY` (CI mock/offline; coleta ao vivo é local, navegador headful).

## Propósito do repositório

Compara o preço de oferta na Liga Pokémon (BR, R$) com o preço de referência do
TCGplayer (USD, pokemontcg.io), converte tudo para BRL e lista os cards
aprovados ordenados por maior margem:

```
Margem% = ((TCG_BRL − Liga_BRL) / Liga_BRL) × 100   (margem BRUTA, sem taxas)
Aprovado  ⇔  preço_liga ≥ R$50  E  margem ≥ 30%
```

> **Margem é BRUTA**: só a diferença de preço entre os dois produtos. O scanner
> NÃO embute frete, taxa de cartão, IOF nem qualquer outra taxa — o operador
> calcula isso por fora, manualmente. O piso de R$50 é filtro de relevância
> (não é taxa). Regra cross-scanner do operador (2026-06-06): 30% bruta, todos
> os scanners de TCG. Os limiares moram em `src/pricing/margin.py`
> (`MIN_MARGIN=30%`, `MIN_PRICE=R$50`).

## Como rodar

```bash
pip install -r requirements.txt
python -m pytest -q       # suíte de testes (204 testes verificados em 2026-08-12)
python src/main.py        # roda o scanner (default: tudo mock, sem internet)
                          # -> reports/report_<timestamp>.{json,csv,xlsx}

# SCAN AO VIVO (coleta o site de verdade + relatório completo, um comando):
python src/collect_liga_live.py --sets PRE          # 1 set
python src/collect_liga_live.py --sets PRE SSP JTG  # vários sets
python src/collect_liga_live.py --sets PRE --resume # retoma scan que caiu
```

Flags do `collect_liga_live.py` (verificadas no argparse):

- `--sets` (obrigatória) — códigos de set da Liga (ex.: `PRE SSP`); aceita
  também a forma `CODIGO=Nome Em Ingles` para set fora do mapa conhecido.
- `--resume` — retoma do checkpoint (`data/liga_live_state.json`).
- `--max-cards N` — limita às N primeiras cartas de cada set (smoke/teste).
- `--min-price` — piso em R$ do pré-filtro da listagem (default `50.0`).
- `--headless` — Chrome invisível (AVISO: o Cloudflare costuma barrar headless;
  o padrão headful é o que funciona).
- `--csv PATH` — onde salvar o CSV de ofertas (default `data/liga_offers.csv`).
- `--no-report` — só coleta e salva o CSV; não roda o relatório TCG no final.

Windows (PC do operador): `01_setup.ps1` → `02_scan_liga.ps1` → `03_scan_real.ps1`
(ver `INSTALL_WINDOWS.md`; existem também os equivalentes `.bat`). Nos comandos
Python do Windows use `.venv\Scripts\python.exe`.

> 🎯 **Skill `scan-liga`** (`.claude/skills/scan-liga/SKILL.md`): fixa o
> procedimento único de scan + a entrega obrigatória no formato padrão MYP +
> a regra do piso (R$50 só para cartas; selados sem piso — ver seção 📤).
> **Todo scan/entrega da Liga passa por ele.** Há também o comando `/auto`
> (`.claude/commands/auto.md`), o modo autônomo padrão da frota.

## 📤 Entrega de resultados — tabela markdown no chat, NUNCA arquivo (MANDATÓRIO)

**Regra dura (operador, 2026-06-06). Vale para TODOS os scanners (CardTrader / MYP / Liga / sealed / PSA).**

O resultado de um scan é entregue ao operador **como tabela markdown no chat do
Claude Code** — no **terminal ou no app**. **NÃO** entregar como arquivo
`.xlsx`/`.csv` para download por padrão.

### A entrega é SEMPRE gerada pela ferramenta do repo — nunca montada à mão

A tabela de entrega é produzida por **`src/reporting/markdown.py`
(`build_markdown`)**, que o `src/main.py` imprime automaticamente no fim de
todo scan. **NÃO** transcrever números do CSV/JSON/XLSX para uma tabela escrita
na mão — isso introduz erro e perde colunas. Sempre rode o pipeline e copie a
tabela que ele imprime:

```bash
# scan ao vivo (coleta + relatório + imprime a tabela markdown):
python src/collect_liga_live.py --sets PRE

# a partir de um CSV de ofertas já coletado (imprime a mesma tabela):
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

(`python src/main.py` em modo mock também imprime a tabela.)

### Formato canônico da tabela (o que `build_markdown` emite) — padrão MYP

Desde 2026-07-02 a entrega é o **formato padrão da frota** (espelho do
`myp_summary.py` do repo `myp-arbitrage-scanner`), em **3 buckets**:

1. **🟢 Aprovados (match exato)** — margem em **negrito**:
   `| # | Margem % | Liga R$ | TCG US$ | Dif | Carta | Set | Raridade | Cond | Qtd | Links |`
2. **⚠️ Aprovados com match fuzzy (validar manualmente)** — mesmas colunas + `Match` (score); o caveat fica no título da seção (padrão MYP), não numa coluna Nota.
3. **❌ Reprovados (margem < 30% ou preço < R$50)** — mesmas colunas + `Match`; garante o invariante da frota de mostrar **TODAS** as linhas comparadas (não amostra curada).

- **Carta** = nome **+ número**, SEM `#` (ex. `Umbreon ex 161`, estilo MYP). O número vem de `Comparison.card_number`; sem número, só o nome; não duplica se já está no nome.
- **Dif** = lucro bruto em R$ (`TCG R$ − Liga R$`).
- **Raridade** / **Qtd** = `—` (a Liga não expõe raridade nem estoque por oferta); **Cond** = `NM` (invariante NM-only).
- **Links** = `[oferta](url) · [TCG](url)` — **clicáveis e verificáveis**, SEMPRE os dois lados quando existirem (a oferta na Liga e a referência de preço no TCGplayer). Nunca inventar URL.
- Formatação: `R$800,00` / `US$300.00` / `95.0%`; `—` para valor ausente. ⚠️ **Gotcha do `fmt_pct`:** a margem da Liga já é percentual — o `fmt_pct` local NÃO multiplica por 100 (diferente do MYP, onde a margem é fração).
- Colunas `Status`/`Nota` NÃO existem (saíram em 2026-07-02 — o bucket codifica o status).
- O procedimento completo de scan + entrega está fixado no skill **`.claude/skills/scan-liga/SKILL.md`**.

### Piso de preço — SÓ para cartas

O piso de **R$50** (`MIN_PRICE_BRL` em `src/pricing/margin.py`) é filtro de
relevância que vale **apenas para cartas avulsas**. **Produtos selados (ETB,
booster box, bundle, tin etc.) NÃO têm piso de preço** — regra do operador
(2026-07-02). Selados nem são escopo deste scanner (a Liga aqui é
singles-only); eles moram no repo `sealed-scanner`. Se um dia este scanner
cobrir selados, o piso NÃO se aplica a eles.

### Arquivo só sob pedido explícito

- O scanner **pode escrever** `reports/report_*.{json,csv,xlsx}` como subproduto local (gitignorado/efêmero) — tudo bem. O ponto é a **ENTREGA**: ela é a tabela markdown no chat, não um anexo.
- Gerar/anexar arquivo (`SendUserFile`) **só quando o operador pedir explicitamente** (ex.: "me manda o XLSX pra importar em lote"). Sem pedido = sem arquivo.

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
- **URL de listagem exige `edid`** (armadilha nº 3, fix #39): a Liga mudou o
  roteamento (2026-06) e a URL de listagem passou a **exigir o `edid` numérico**
  além do código do set — a URL antiga (`?view=cards/search&card=ed=CODE`) cai
  na home SEM cartas. O coletor extrai o mapa `{CODIGO: edid}` da página de
  edições e monta a URL com os dois (`edid` + `ed` no mesmo parâmetro `card=`).
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
| `LIGA_OFFERS_CSV` | `data/liga_offers.csv` | path — header `card_name,set_name,price_brl,url[,condition,seller,card_number]`; linha com `condition` explícita ≠ `NM` (match EXATO) é pulada com aviso (invariante NM-only; coluna ausente/vazia = NM) |
| `LIGA_SETS` | — | códigos de set p/ `live` via env (ex. `PRE,SSP`); a CLI `collect_liga_live.py` é o caminho preferido |
| `LIGA_LIVE_HEADLESS` | — | `1` = Chrome headless no modo `live` via env (mesmo aviso da flag `--headless`) |
| `LIGA_LIVE_RESUME` | — | `1` = retoma do checkpoint no modo `live` via env (equivale a `--resume`) |
| `LIGA_TCG_SOURCE` | `mock` | `mock` / `csv` / `pokemontcg` / `api` (stub) |
| `LIGA_TCG_CSV` | `data/tcgplayer_prices.csv` | path — header `card_name,set_name,market_price_usd[,url]` |
| `LIGA_POKEMONTCG_CACHE_DIR` | `data/cache/pokemontcg` | path / vazio (desabilita cache) |

Caminho de produção manual (você fornece só as ofertas; o preço TCG vem automático):

```bash
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

O scanner integrado (repo `integrated-scanner`; pasta local no PC do operador
`C:\Users\mathe\integrated-scanner`) consome exatamente esse caminho: ele roda
`src/main.py` com `LIGA_OFFERS_SOURCE=csv` se existir `data/liga_offers.csv`
real — que é o arquivo que `collect_liga_live.py` gera. Fluxo: coletar ao vivo
aqui → integrado lê sozinho.

Os CSVs reais (`liga_offers.csv`, `tcgplayer_prices.csv`) estão no
`.gitignore`. Para os modos `csv`/`mock` há dados de exemplo versionados:
`data/liga_offers.example.csv`, `data/tcgplayer_prices.example.csv`,
`data/liga_offers_mock.json`, `data/tcgplayer_prices_mock.json`.

## Testes

```bash
python -m pytest -q    # pytest.ini na raiz (testpaths=tests, pythonpath=.)
```

204 testes (contagem verificada por `pytest --collect-only -q` em 2026-08-12 —
se divergir, o número real vence). Suíte offline: os testes exercitam
parsers/helpers puros; o browser é importado lazy e nunca é lançado.

**CI — UM workflow** (Python 3.11, dispara em push na `main` e em todo PR):

- `.github/workflows/ci.yml` ("CI"): `pytest -q` + smoke do scanner com dados
  mock (`python src/main.py` com `LIGA_USD_BRL_RATE=5.20`).
- (O antigo `tests.yml`, redundante, foi removido no PR #46, 2026-07-07.)

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
  card_matcher.py        match_cards() -> Comparison.  exato por número -> exato (chave normalizada) -> fuzzy difflib (nome .7 / set .3, thr .82); ordena por margem. Comparison carrega card_number (p/ a coluna Carta) + match_score (fuzzy => "validar manualmente")
  normalization.py       lowercase, remove acento, aliases de set (obf -> obsidian flames...), VMAX/VSTAR/VUNION
src/pricing/
  currency.py            get_exchange_rate() (fixo / auto via AwesomeAPI); convert_usd_to_brl()
  margin.py              calculate_margin(); is_approved().  MIN_MARGIN=30% (bruta, sem taxa), MIN_PRICE=R$50
src/reporting/
  markdown.py            build_markdown() — a ENTREGA canonica (tabela markdown formato MYP, 3 buckets, links clicaveis). main.py imprime isto no fim.
  xlsx.py                write_xlsx() — header colorido, formato moeda/%, tinta por status, hyperlinks, freeze panes, autofilter (subproduto local)
```

## Convenções e gotchas

- **Dependências (requirements.txt):** o pipeline de relatório usa `urllib`
  (stdlib) para HTTP + `openpyxl` para o XLSX; o coletor ao vivo trouxe
  `patchright` (Chrome real anti-detect), `beautifulsoup4` (parser HTML, com o
  `html.parser` da stdlib — **não** precisa de `lxml`) e `pillow`+`numpy`
  (template matching do preço). `requests` e `lxml` seguem fora — **não
  readicionar dependência sem uso real**.
- **Coletores nunca abortam o pipeline por dado ruim**: pulam a linha inválida com `logger.warning` e seguem.
- **`http` (Liga) e `api` (TCGplayer) são stubs propositais** — Liga bloqueia clientes não-browser (403) e o TCGplayer oficial exige credenciais. O brief proíbe burlar bloqueios; use `csv` ou `pokemontcg`.
- **pokemontcg.io**: para cards com várias versões no mesmo set, escolhe a de **menor `market`** (assume que a Liga lista a versão regular).

## Fluxo de desenvolvimento e segurança

- **Branch + PR, nunca push direto em `main`** (padrão da frota; o estado real
  do projeto mora no código mergeado em `main` — branches/PRs são propostas).
- **Sem CHANGELOG.md nem marcador de versão** neste repo: a fonte de verdade de
  "estado atual" é o `main` + o histórico de PRs (ver seção Estado abaixo).
- **Dados de scan ficam FORA do repo público**: CSVs reais e
  `reports/report_*.{json,csv,xlsx}` são gitignorados. Chaves/segredos
  (`POKEMONTCG_API_KEY`) nunca versionados.
- **README.md é minimalista DE PROPÓSITO** (release público discreto — espelha
  o template do CardTrader/COMC): título neutro `price-compare-tool`, sem
  Pokémon/Liga/TCG/arbitragem nem árvore de arquitetura. **NÃO "consertar"
  re-adicionando seções "Estrutura"/"Próximos passos"** — isso reexporia o caso
  de uso e regrediria a discrição do release público. A doc técnica canônica
  (arquitetura, módulos, fluxo) é **este `CLAUDE.md`**, não o README. *(A antiga
  pendência de "doc drift no README" foi resolvida por essa sanitização — as
  seções desatualizadas deixaram de existir.)* Ver também
  `PUBLIC-RELEASE-CHECKLIST.md` e `SECURITY.md` na raiz.

## 🔌 Plugins do Claude Code (setup do operador, todos os repos)

Decisão do operador (2026-09-11): plugins instalados **globalmente** (scope `user`,
que é o default do CLI — grava em `C:\Users\mathe\.claude\settings.json` e vale em
qualquer repo). **NÃO declarar em `.claude/settings.json` do repo**: seria uma
segunda fonte de verdade (project scope) e ainda dependeria do prompt de
workspace trust. Rodar **uma vez** no PowerShell do PC:

```powershell
# 1) marketplaces-fonte — nenhum dos tres vive em anthropics/claude-code (repo de DEMOS)
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add thedotmack/claude-mem
claude plugin marketplace add kingbootoshi/cartographer

# 2) install — sem --scope de proposito: default 'user' = todos os repos
claude plugin install claude-code-setup@claude-plugins-official
claude plugin install claude-mem@thedotmack
claude plugin install cartographer@cartographer-marketplace

claude plugin list   # conferir; depois reabrir o Claude (ou /reload-plugins)
```

| Plugin | Origem | O que traz |
|---|---|---|
| `claude-code-setup` | **Anthropic (oficial)** | 1 skill: analisa o codebase e sugere hooks/skills/MCP/subagents sob medida |
| `claude-mem` | terceiro (`thedotmack`) | memória persistente entre sessões: 20 skills, 6 hooks, 1 MCP (`mcp-search`) |
| `cartographer` | terceiro (`kingbootoshi`) | 1 skill: mapeia o codebase com subagents em paralelo → `docs/CODEBASE_MAP.md` |

Todas as skills são *model-invoked* (nenhuma tem `disable-model-invocation`): o
Claude dispara sozinho quando a tarefa casa com a descrição. Os hooks do
`claude-mem` rodam em toda sessão sem pedir.

Ressalvas:

- **`claude-mem` é o caro dos três**: ~2.000 tokens *always-on* + hook `PostToolUse`
  disparando um worker node a cada chamada de ferramenta. Em scan ao vivo da Liga
  (centenas de páginas, Chrome headful) isso pesa — `claude plugin disable claude-mem`
  antes do scan se atrapalhar. Depende de disco persistente (`~/.claude-mem`) e de
  `node` no PATH: em sessão remota (container efêmero) a memória morre junto; o
  valor dele é no PC.
- **Podar skills fora de escopo** (opcional), em `C:\Users\mathe\.claude\settings.json`
  → `"skillOverrides": { "claude-mem:<skill>": "off" }` para `wowerpoint`,
  `design-is`, `standup`, `weekly-digests`, `timeline-report`, `oh-my-issues`,
  `version-bump`, `mode-creator`, `ccs-align`. `"off"` some do contexto e do menu
  `/`; `"user-invocable-only"` some do contexto mas ainda responde ao `/`. Mantém o
  núcleo de memória (`mem-search`, `pathfinder`, `smart-explore`, `learn-codebase`,
  `make-plan`).
- **Dois são de terceiros** e registram hooks que executam comandos locais;
  `claude plugin update <nome>` puxa código novo desses repos — atualizar de forma
  consciente.
- **`cartographer` gasta tokens de verdade** (subagents em paralelo sobre o codebase
  inteiro): rodar sob demanda, não em loop.

## Ambiente do operador — OmniRoute (fora do pipeline)

`OMNIROUTE.md` na raiz documenta como ligar o **Claude Code** a um gateway
OmniRoute local para que, **quando a cota de um modelo acaba, a cadeia (combo)
troque de modelo sozinha**. É manual de ambiente: o scanner é Python puro e
**não chama LLM nenhum** — nada ali muda scan, margem, piso ou entrega.

Duas decisões que valem como regra: (1) **nunca** versionar
`.claude/settings.json` com `ANTHROPIC_BASE_URL` apontando pro gateway — settings
de projeto também valem nas sessões do Claude Code na nuvem, que não enxergam
`127.0.0.1:20128`, e isso quebraria toda sessão remota; o ambiente entra no shell
que abre o Claude Code. (2) Token `oma_live_...` **nunca** versionado, e salvo
**sem BOM** (erro recorrente nº 1 da frota).

## Decisões

Martelos batidos pela operadora (destino do balde 2 do `/reflect`). Uma linha
por decisão: **decisão + data + motivo**; quando a regra tem seção própria, o
item aponta pra ela (fonte única, sem cópia).

- **Margem BRUTA, mínimo 30%, em todos os scanners de TCG** (2026-06-06) —
  taxas o operador calcula por fora. → § Propósito do repositório.
- **Entrega = tabela markdown no chat, nunca arquivo por padrão** (2026-06-06)
  — arquivo só sob pedido explícito. → § 📤 Entrega de resultados.
- **Selados não têm piso de preço** (2026-06-27) — o piso é filtro de
  relevância de single. → § Convenções da frota.
- **Piso R$50 só para cartas + formato padrão MYP na entrega** (2026-07-02,
  PR #41). → § 📤 Entrega de resultados.
- **Coleta nova a cada solicitação; nenhum resultado no GitHub** (2026-09-06)
  — nunca reutilizar preço de outro scan. → `DELIVERY_CHAT.md`.
- **Nunca versionar `.claude/settings.json` com `ANTHROPIC_BASE_URL`; token do
  gateway sem BOM** — quebraria toda sessão de nuvem. → § OmniRoute.
- **`/reflect` grava em `CLAUDE.md` + `scanners-commons`, não em memória, e
  mostra antes de salvar** (2026-09-12, PR #53) — memória não viaja pra sessão
  de nuvem. → `.claude/skills/reflect/SKILL.md`.

## Estado, pendências e histórico

Histórico condensado (mais recente primeiro; detalhes normativos nas seções próprias):

- **#44 (2026-07-06)** — honestidade de câmbio/preço (guard contra câmbio
  não-positivo) + fix de crash cp1252 no Windows.
- **#42** — sync do skill `/auto` v3.2 da frota (execução segura de runs longos).
- **#39 (fix liga-live)** — a Liga mudou o roteamento: URL de listagem passou a
  exigir `edid` (ver armadilha nº 3 na seção do coletor ao vivo).
- **#41 (2026-07-02)** — entrega alinhada ao **formato padrão MYP** + skill
  `scan-liga` + regra do piso só-cartas: `build_markdown` reescrito no formato
  canônico da frota (3 buckets, colunas padrão, links `[oferta] · [TCG]`,
  saíram as colunas `Status`/`Nota`). Formato completo + gotcha do `fmt_pct` na
  seção 📤 (fonte única — não duplicar aqui).
- **2026-06-17** — entrega canônica em tabela markdown: `build_markdown` virou a
  saída de entrega, impressa pelo `main.py` no fim de todo scan (substituiu a
  tabela de texto fixo); `Comparison` ganhou `card_number` e links clicáveis;
  match fuzzy → "validar manualmente".
- PRs #15 e #16 mergeados (histórico); `main` funcional, CI verde.

Pendências vivas:

- **Apagar branches órfãs** (era a "issue #17" — o repo tem issues
  DESABILITADAS, a API responde 410; a tarefa vive só aqui). Bloqueio real
  (2026-09-12): o classificador de permissão da sessão de nuvem nega
  `git push --delete` como ação destrutiva, e o GitHub MCP não apaga branch —
  é ação manual da operadora. Auditoria de 2026-09-12 (`git merge-tree` contra
  `origin/main`): **5 branches são no-op** (mergear não muda nada na `main`) e
  podem ir sem perda —
  `claude/plugin-installation-setup-cb94ve`,
  `claude/pokemon-cards-scanner-review-yqm1vy`,
  `claude/pokemon-scanner-singles-dyzu9a`,
  `claude/self-evolving-agent-integration-budf77`,
  `feat/chat-only-delivery`.
  As demais **têm conteúdo fora da `main`** (proposta não mergeada, ou PR
  aberto — #52 graphify, #54 sync-auto) e pedem decisão, não limpeza.
  Comando (PC do operador): `git push origin --delete <branch>`.
- **Arquivar o repositório duplicado `liga-arbitrage-scanner`** — em
  2026-09-12 ele **não aparece** na lista de repos acessíveis à conta na nuvem
  (`list_repos` com "liga"/"arbitrage" só devolve este repo, `myp-` e `ebay-`).
  Ou já foi arquivado/apagado, ou a sessão não o enxerga: conferir no GitHub;
  se existir, arquivar em Settings → Danger Zone (não há ferramenta MCP).
- **Os 4 baldes do `/reflect` foram definidos neste repo** — o anexo com a
  estrutura da versão de chat do skill (que grava na memória) não chegou na
  sessão, e o `scanners-commons` não tem nenhum `/reflect` pra comparar
  (verificado 2026-09-12). Conferir com a versão do chat antes de tratar o
  formato como padrão da frota.
- **(proposta) Levar o `/reflect` pra frota pelo `scanners-commons`** — como o
  `/auto` (mestra em `tooling/auto.md` + `tooling/sync-auto-skill.sh` para os
  8 repos). Hoje o skill só existe aqui; sem isso cada scanner terá a sua
  cópia divergente.
