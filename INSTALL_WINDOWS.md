# Instalação no Windows (passo-a-passo)

Guia para quem nunca rodou Python antes. Objetivo: chegar ao ponto de
duplo-clique em `02_scan_liga.bat` e receber a planilha de deals.

Tempo total estimado: **10 minutos** (uma vez só).

---

## 1. Instalar o Python

1. Acesse https://www.python.org/downloads/ no seu navegador.
2. Clique no botão amarelo **"Download Python 3.x.x"** no topo da página.
   Pega a versão mais recente automaticamente.
3. Abra o arquivo baixado (`python-3.x.x-amd64.exe` na pasta Downloads).
4. **IMPORTANTE**: na primeira tela do instalador, marque a caixa
   **"Add Python to PATH"** (fica embaixo). Sem isso o resto não funciona.
5. Clique em **"Install Now"** e espere terminar (1-2 min).
6. Quando aparecer "Setup was successful", clique **Close**.

### Verificar que funcionou

Abra o **PowerShell** (aperte Win+R, digite `powershell`, Enter) e cole:

```powershell
python --version
```

Deve mostrar algo como `Python 3.13.0`. Se mostrar erro
"python não é reconhecido", o passo 4 não foi feito — reinstale marcando
a caixa "Add to PATH".

## 2. Baixar este repositório

Você tem duas opções. A mais fácil é o ZIP:

### Opção A — Download ZIP (mais simples)

1. Acesse https://github.com/matheuscllm-lgtm/liga-pokemon-scanner
2. Botão verde **"Code"** → **"Download ZIP"**.
3. Extraia o ZIP num lugar fácil (ex: `C:\Users\seu_usuario\Documents\liga-pokemon-scanner`).

### Opção B — Git clone (se já tem git)

```powershell
cd $HOME\Documents
git clone https://github.com/matheuscllm-lgtm/liga-pokemon-scanner.git
```

## 3. Setup inicial (uma única vez)

1. Abra a pasta do projeto no Explorer.
2. **Duplo-clique** em `01_setup.bat`.
3. Vai abrir uma janela preta (PowerShell). Espere até aparecer:

   ```
   ==> Setup concluido. Use .\02_scan_liga.ps1 para rodar o scanner.
   Pressione Enter para sair...
   ```

4. Aperte Enter. Pronto, setup terminou.

O que aconteceu: criou uma pasta `.venv` com Python isolado e instalou
as bibliotecas necessárias. Não precisa repetir esse passo a menos
que mude o `requirements.txt`.

## 4. Rodar o scanner

O scanner tem três modos prontos com 1 clique cada.

### Modo mock (teste rápido — confirma instalação)

1. Duplo-clique em `02_scan_liga.bat`.
2. Aparece tabela no terminal + 3 arquivos em `reports/`:
   `report_<timestamp>.{json,csv,xlsx}`. Abra o **.xlsx** no Excel.

### Modo produção (Liga CSV + TCG ao vivo) — **recomendado**

Caminho final do produto: você cura o CSV de ofertas Liga, o lado TCG
vem 100% sozinho da API pública pokemontcg.io.

1. Copie `data/liga_offers.example.csv` para `data/liga_offers.csv`.
2. Edite com as ofertas que você quer monitorar. Header obrigatório:
   `card_name,set_name,price_brl,url`. Opcionais: `condition`, `seller`.
3. Duplo-clique em **`03_scan_real.bat`**.

A primeira execução é mais lenta (~1s por card) porque consulta a API.
A segunda execução usa cache em disco e é instantânea (cache TTL 24h
em `data/cache/`).

Pra usar câmbio ao vivo (AwesomeAPI), rode no PowerShell:

```powershell
.\03_scan_real.ps1 -Live
```

### Modo CSV puro (dois lados manuais)

Se quiser ter o controle total dos preços de referência:

1. Copie `data/tcgplayer_prices.example.csv` para
   `data/tcgplayer_prices.csv` e edite.
2. No PowerShell:

   ```powershell
   $env:LIGA_OFFERS_SOURCE = "csv"
   $env:LIGA_TCG_SOURCE = "csv"
   .\02_scan_liga.ps1
   ```

   Ou edite `scanner.config` (criado a partir de `scanner.config.example`)
   pra fixar a taxa USD→BRL.

A planilha sai com cabeçalho colorido, linhas verde claro para deals
aprovados (margem ≥ 25%, preço ≥ R$50) e rosa para reprovados.

## 5. Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| "python não é reconhecido" | Esqueceu de marcar "Add Python to PATH" | Reinstale Python marcando a caixa |
| Janela preta fecha rápido demais | Crash no script | Abra PowerShell, navegue até a pasta com `cd`, rode `.\01_setup.ps1` direto pra ver o erro |
| "Cannot find module 'openpyxl'" | Setup não rodou | Rode `01_setup.bat` antes de `02_scan_liga.bat` |
| Scanner.config / liga_offers.csv não existe | Arquivos locais não criados | Copie os `.example` (instruções acima) |
| Taxa USD→BRL antiga | Default é 5.20 | Defina `$env:LIGA_USD_BRL_RATE = "5.35"` antes de rodar, ou edite `scanner.config` |

## 6. Próximas evoluções já planejadas

- **Coletor TCGplayer real** via pokemontcg.io (sem mais CSV manual desse lado) — implementado em PR mas ainda não integrado.
- **Coletor Liga via HTTP** (precisa rodar do seu IP residencial — funciona da sua máquina mas não de servidores em nuvem) — backlog.
- **Câmbio ao vivo** (AwesomeAPI) com fallback fixo — backlog.

Cada um vira um botão a menos pra você clicar.
