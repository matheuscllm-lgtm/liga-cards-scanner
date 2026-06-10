# Liga Pokémon Scanner

Scanner de arbitragem para comparar preços de cards Pokémon entre Liga
Pokémon e TCGplayer, com todos os valores convertidos para reais.

## Objetivo

Encontrar cards vendidos na Liga Pokémon com potencial de arbitragem em
relação ao preço de referência do TCGplayer.

## Critérios

- Margem bruta mínima: 30%
- Preço mínimo do card: R$50
- Moeda de saída: BRL
- Comparação: Liga Pokémon vs TCGplayer
- Foco: cards individuais

> **Margem BRUTA = só a diferença de preço entre o card na Liga e a referência
> no TCGplayer.** O scanner NÃO desconta nenhuma taxa (frete, cartão, IOF, etc.).
> Essas taxas você (operador) calcula por fora, à mão, depois de escolher o card.
> O piso de R$50 é só um filtro de relevância (ignora cards baratos), não uma taxa.

## Fórmula de margem

```
Margem bruta (%) = ((Preço TCGplayer em BRL - Preço Liga Pokémon) / Preço Liga Pokémon) * 100
```

### Exemplo

Se um card custa R$80 na Liga Pokémon e o preço equivalente no TCGplayer
é R$110:

```
Margem = ((110 - 80) / 80) * 100 = 37,5%
```

Resultado: aprovado, pois a margem bruta é maior que 30%.

## Estrutura

```text
liga-pokemon-scanner/
├── src/
│   ├── collectors/
│   │   ├── liga_pokemon.py
│   │   ├── pokemontcg.py
│   │   └── tcgplayer.py
│   ├── pricing/
│   │   ├── currency.py
│   │   └── margin.py
│   ├── matching/
│   │   ├── card_matcher.py
│   │   └── normalization.py
│   ├── reporting/
│   │   └── xlsx.py
│   └── main.py
├── data/
│   ├── liga_offers_mock.json
│   └── tcgplayer_prices_mock.json
├── reports/
├── requirements.txt
└── README.md
```

## Como rodar

> **Windows / nunca rodei Python antes?** Veja
> [`INSTALL_WINDOWS.md`](INSTALL_WINDOWS.md) — passo-a-passo de 10 minutos.

### Windows / PowerShell (padrão MyP)

Duplo-clique nos `.bat` (ou rode os `.ps1` no terminal):

1. `01_setup.bat` — encontra Python 3.10+, cria `.venv`, instala
   `requirements.txt` + `pytest`. Log em `logs/setup_<timestamp>.log`.
2. `02_scan_liga.bat` — roda o scanner em modo mock.
3. `03_scan_real.bat` — roda o scanner no caminho de produção
   (Liga CSV + pokemontcg.io). Requer `data/liga_offers.csv` curado.

Logs em `logs/scan_<timestamp>.log`. Relatórios em `reports/`.

Taxa USD->BRL: copie `scanner.config.example` para `scanner.config` e
edite, ou passe via parâmetro:

```powershell
.\02_scan_liga.ps1 -Rate 5.35
```

### Linux / macOS / qualquer ambiente com Python

```bash
pip install -r requirements.txt
python src/main.py
```

A taxa USD->BRL pode ser sobrescrita via variável de ambiente:

```bash
LIGA_USD_BRL_RATE=5.35 python src/main.py
```

Cada execução gera três arquivos em `reports/`:

- `report_<timestamp>.json`
- `report_<timestamp>.csv`
- `report_<timestamp>.xlsx`

todos ordenados por maior margem.

## Modos do scanner

O scanner alterna fonte de dados via variáveis de ambiente. Default: tudo mock.

| Variável | Default | Valores | Efeito |
|---|---|---|---|
| `LIGA_USD_BRL_RATE` | `5.20` | float / `auto` | Taxa USD→BRL. `auto` busca cotação ao vivo na AwesomeAPI com fallback para 5.20. |
| `LIGA_OFFERS_SOURCE` | `mock` | `mock` / `csv` / `live` / `http` | Fonte das ofertas Liga Pokémon (`live` = coleta ao vivo com Chrome). |
| `LIGA_OFFERS_CSV` | `data/liga_offers.csv` | path | Caminho do CSV quando `LIGA_OFFERS_SOURCE=csv`. |
| `LIGA_TCG_SOURCE` | `mock` | `mock` / `csv` / `pokemontcg` / `api` | Fonte das referências TCGplayer. |
| `LIGA_TCG_CSV` | `data/tcgplayer_prices.csv` | path | Caminho do CSV quando `LIGA_TCG_SOURCE=csv`. |
| `LIGA_POKEMONTCG_CACHE_DIR` | `data/cache/pokemontcg` | path / vazio | Diretório de cache em disco (TTL 24h). Vazio desabilita. |

### Modo `mock` (default)

Lê `data/tcgplayer_prices_mock.json` e `data/liga_offers_mock.json`. É o
caminho do CI e dos testes — não precisa de internet, credenciais ou
arquivos extras.

### Modo `csv` (fallback manual)

Padrão do brief — Liga bloqueia clientes não-browser e TCGplayer exige
credenciais. Solução: exportar manualmente os dois lados.

**Ofertas Liga Pokémon:**

1. Copie o template e edite com as ofertas:
   ```bash
   cp data/liga_offers.example.csv data/liga_offers.csv
   ```
   Header obrigatório: `card_name,set_name,price_brl,url`.
   Opcionais: `condition` (default `NM`), `seller`.
2. Rode:
   ```bash
   LIGA_OFFERS_SOURCE=csv python src/main.py
   ```

**Referências TCGplayer:**

1. Mesmo padrão:
   ```bash
   cp data/tcgplayer_prices.example.csv data/tcgplayer_prices.csv
   ```
   Header: `card_name,set_name,market_price_usd[,url]`.
2. Rode:
   ```bash
   LIGA_TCG_SOURCE=csv python src/main.py
   ```

Os dois ao mesmo tempo (caminho de produção atual):

```bash
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=csv python src/main.py
```

Os arquivos `data/liga_offers.csv` e `data/tcgplayer_prices.csv` reais
estão no `.gitignore` — não são commitados.

### Modo `pokemontcg` (TCGplayer real, sem credenciais)

Consulta a API pública [`pokemontcg.io`](https://pokemontcg.io/) para
cada par (card_name, set_name) **derivado das ofertas Liga** — só
precisa fornecer as ofertas, o preço TCG vem automático:

```bash
LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py
```

Sem auth, sem chave. Aplica `delay_after=1s` por requisição para
respeitar rate limit. Cards com várias versões no mesmo set (regular,
full art) são desambiguados pegando a de menor preço de mercado
(assume Liga vende a regular).

### Modo `live` (coleta ao vivo da Liga — o caminho completo)

Coleta o site de verdade com **Google Chrome headful** (janela visível)
controlado por `patchright`. Comando único que coleta E gera o relatório:

```bash
python src/collect_liga_live.py --sets PRE          # 1 set
python src/collect_liga_live.py --sets PRE SSP JTG  # vários
python src/collect_liga_live.py --sets PRE --resume # retoma scan que caiu
```

Filtra EN + NM exato, decodifica o preço anti-scraping da Liga, salva
checkpoint pra retomar, e grava `data/liga_offers.csv` (o mesmo que o
scanner integrado consome). Detalhes técnicos no `CLAUDE.md` (seção
"Coletor ao vivo").

### Modos `http` (Liga) e `api` (TCGplayer)

Stubs que levantam `NotImplementedError`. `http` (urllib puro) nunca vai
funcionar — a Liga retorna 403 para clientes não-browser; use o modo
`live`. TCGplayer oficial exige credenciais.

## Saída esperada

A lista priorizada inclui, para cada card:

- Nome do card
- Set
- Preço na Liga Pokémon (R$)
- Preço de referência no TCGplayer (USD e BRL)
- Margem estimada (%)
- Câmbio utilizado na conversão
- Link da oferta na Liga Pokémon
- Link de referência no TCGplayer
- Status: `approved` ou `rejected`

## Próximos passos

- Integrar com a API oficial do TCGplayer (credenciais necessárias).
- Melhorar o matcher (normalização, aliases, sets em PT/EN).
- Ampliar o mapa de sets do coletor ao vivo (`ED_SETS` em
  `src/collectors/liga_live.py`) conforme novos lançamentos.

## Status

Funcional ponta a ponta: coletor AO VIVO da Liga (Chrome headful) +
preços reais do TCGplayer via pokemontcg.io. O modo mock continua sendo
o default (CI/testes).
