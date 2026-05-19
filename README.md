# Liga Pokémon Scanner

Scanner de arbitragem para comparar preços de cards Pokémon entre Liga
Pokémon e TCGplayer, com todos os valores convertidos para reais.

## Objetivo

Encontrar cards vendidos na Liga Pokémon com potencial de arbitragem em
relação ao preço de referência do TCGplayer.

## Critérios iniciais

- Margem mínima: 25%
- Preço mínimo do card: R$50
- Moeda de saída: BRL
- Comparação: Liga Pokémon vs TCGplayer
- Foco: cards individuais

## Fórmula de margem

```
Margem (%) = ((Preço TCGplayer em BRL - Preço Liga Pokémon) / Preço Liga Pokémon) * 100
```

### Exemplo

Se um card custa R$80 na Liga Pokémon e o preço equivalente no TCGplayer
é R$110:

```
Margem = ((110 - 80) / 80) * 100 = 37,5%
```

Resultado: aprovado, pois a margem é maior que 25%.

## Estrutura

```text
liga-pokemon-scanner/
├── src/
│   ├── collectors/
│   │   ├── liga_pokemon.py
│   │   └── tcgplayer.py
│   ├── pricing/
│   │   ├── currency.py
│   │   └── margin.py
│   ├── matching/
│   │   └── card_matcher.py
│   └── main.py
├── data/
│   ├── liga_offers_mock.json
│   └── tcgplayer_prices_mock.json
├── reports/
├── requirements.txt
└── README.md
```

## Como rodar

```bash
pip install -r requirements.txt
python src/main.py
```

A taxa USD->BRL pode ser sobrescrita via variável de ambiente:

```bash
LIGA_USD_BRL_RATE=5.35 python src/main.py
```

Cada execução gera dois arquivos em `reports/`:

- `report_<timestamp>.json`
- `report_<timestamp>.csv`

ambos ordenados por maior margem.

## Modos do scanner

O scanner alterna fonte de dados via variáveis de ambiente. Default: tudo mock.

| Variável | Default | Valores | Efeito |
|---|---|---|---|
| `LIGA_USD_BRL_RATE` | `5.20` | float | Taxa USD→BRL usada na conversão. |
| `LIGA_OFFERS_SOURCE` | `mock` | `mock` / `csv` / `http` | Fonte das ofertas Liga Pokémon. |
| `LIGA_OFFERS_CSV` | `data/liga_offers.csv` | path | Caminho do CSV quando `LIGA_OFFERS_SOURCE=csv`. |
| `LIGA_TCG_SOURCE` | `mock` | `mock` / `csv` / `api` | Fonte das referências TCGplayer. |
| `LIGA_TCG_CSV` | `data/tcgplayer_prices.csv` | path | Caminho do CSV quando `LIGA_TCG_SOURCE=csv`. |

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

### Modos `http` (Liga) e `api` (TCGplayer)

Stubs que levantam `NotImplementedError`. Liga retorna 403 para clientes
não-browser, e o brief proíbe burlar bloqueios. TCGplayer exige
credenciais oficiais. Ambos ficam para depois do MVP.

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

- Implementar coletor real da Liga Pokémon respeitando robots.txt e rate limits.
- Integrar com a API oficial do TCGplayer (credenciais necessárias).
- Buscar câmbio ao vivo (ex.: AwesomeAPI / BCB) em vez do fallback fixo.
- Melhorar o matcher (normalização, aliases, sets em PT/EN).

## Status

Projeto em desenvolvimento. Coletores rodam com dados mockados em `data/`.
