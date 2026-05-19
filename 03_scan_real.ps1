<#
.SYNOPSIS
Roda o scanner no caminho de PRODUCAO: ofertas Liga via CSV + precos
TCG ao vivo via pokemontcg.io.

.DESCRIPTION
Requer data/liga_offers.csv (copie de data/liga_offers.example.csv e
edite com ofertas reais). Lado TCG vem da API publica pokemontcg.io
(sem auth, sem credenciais).

Cambio: padrao 5.20. Use -Rate para sobrescrever, ou -Live para buscar
cotacao ao vivo na AwesomeAPI.

.PARAMETER Rate
Sobrescreve taxa USD->BRL. Ex: -Rate 5.35.

.PARAMETER Live
Busca cambio ao vivo (AwesomeAPI). Fallback para 5.20 se falhar.
#>
[CmdletBinding()]
param(
    [string]$Rate,
    [switch]$Live
)

$ErrorActionPreference = "Continue"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logsDir "scan_real_$stamp.log"

$isWin = ($env:OS -eq 'Windows_NT')
$venv = Join-Path $root ".venv"
$venvPython = if ($isWin) {
    Join-Path $venv "Scripts\python.exe"
} else {
    Join-Path $venv "bin/python"
}

function Write-Step {
    param([string]$Msg, [string]$Color = "Cyan")
    Write-Host $Msg -ForegroundColor $Color
    Add-Content -Path $logFile -Value $Msg -Encoding UTF8
}

function Assert-Prereqs {
    Write-Step "[1/4] Verificando pre-requisitos..."
    if (-not (Test-Path $venvPython)) {
        Write-Step "    ERRO: .venv nao encontrado. Rode .\01_setup.ps1 primeiro." "Red"
        throw ".venv ausente."
    }
    $ligaCsv = Join-Path $root "data\liga_offers.csv"
    if (-not (Test-Path $ligaCsv)) {
        $example = Join-Path $root "data\liga_offers.example.csv"
        Write-Step "    ERRO: $ligaCsv nao existe." "Red"
        Write-Step "    Copie $example -> $ligaCsv e edite com ofertas reais." "Yellow"
        throw "liga_offers.csv ausente."
    }
    Write-Step "    .venv OK; liga_offers.csv OK" "Green"
}

function Configure-Env {
    Write-Step "[2/4] Configurando ambiente..."
    $env:LIGA_OFFERS_SOURCE = "csv"
    $env:LIGA_TCG_SOURCE = "pokemontcg"

    if ($Rate) {
        $env:LIGA_USD_BRL_RATE = $Rate
        Write-Step "    Cambio: $Rate (via -Rate)" "Green"
    } elseif ($Live) {
        $env:LIGA_USD_BRL_RATE = "auto"
        Write-Step "    Cambio: AwesomeAPI ao vivo (fallback 5.20)" "Green"
    } else {
        $cfgPath = Join-Path $root "scanner.config"
        if (Test-Path $cfgPath) {
            $line = Get-Content $cfgPath | Where-Object { $_ -match "^\s*USD_BRL_RATE\s*=" } | Select-Object -First 1
            if ($line) {
                $value = ($line -split "=", 2)[1].Trim()
                $env:LIGA_USD_BRL_RATE = $value
                Write-Step "    Cambio: $value (via scanner.config)" "Green"
            }
        } else {
            Write-Step "    Cambio: fallback 5.20" "Yellow"
        }
    }
    Write-Step "    LIGA_OFFERS_SOURCE=csv  LIGA_TCG_SOURCE=pokemontcg" "Green"
}

function Invoke-Scanner {
    Write-Step "[3/4] Rodando scanner (pode demorar ~1s por card no 1o run; cache acelera depois)..."
    $main = Join-Path $root "src\main.py"
    if (-not (Test-Path $main)) {
        $main = Join-Path $root "src/main.py"
    }
    & $venvPython $main 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: scanner falhou (exit $LASTEXITCODE)." "Red"
        throw "Scanner falhou."
    }
}

function Show-LatestReport {
    Write-Step "[4/4] Procurando planilha mais recente..."
    $reportsDir = Join-Path $root "reports"
    $latestXlsx = Get-ChildItem -Path $reportsDir -Filter "report_*.xlsx" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestXlsx) {
        Write-Step "    Planilha: $($latestXlsx.FullName)" "Green"
    } else {
        Write-Step "    Nenhum XLSX encontrado em reports/." "Yellow"
    }
}

try {
    Write-Step "==> Scanner liga-pokemon REAL (log: $logFile)"
    Assert-Prereqs
    Configure-Env
    Invoke-Scanner
    Show-LatestReport
    Write-Step "==> Concluido." "Green"
} catch {
    Write-Step "==> ERRO: $($_.Exception.Message)" "Red"
} finally {
    Read-Host "Pressione Enter para sair..."
}
