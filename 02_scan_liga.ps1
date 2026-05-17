<#
.SYNOPSIS
Roda o scanner liga-pokemon-scanner e gera relatorio CSV + JSON em reports/.

.DESCRIPTION
Padrao MyP: duplo-clique no .bat correspondente (ou rodar via
.\02_scan_liga.ps1). Le a taxa USD->BRL de scanner.config (chave
USD_BRL_RATE=...) ou usa o fallback do Python. Loga em
logs/scan_<timestamp>.log via Tee-Object.

.PARAMETER Rate
Sobrescreve a taxa USD->BRL passada via scanner.config. Ex: -Rate 5.35.
#>
[CmdletBinding()]
param(
    [string]$Rate
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
$logFile = Join-Path $logsDir "scan_$stamp.log"

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

function Assert-Venv {
    Write-Step "[1/3] Verificando .venv..."
    if (-not (Test-Path $venvPython)) {
        Write-Step "    ERRO: .venv nao encontrado em $venvPython." "Red"
        Write-Step "    Rode primeiro: .\01_setup.ps1" "Yellow"
        throw ".venv ausente."
    }
    Write-Step "    .venv OK ($venvPython)" "Green"
}

function Read-Config {
    Write-Step "[2/3] Lendo configuracao..."
    $cfgPath = Join-Path $root "scanner.config"

    if ($Rate) {
        Write-Step "    Taxa USD->BRL via parametro: $Rate" "Green"
        $env:LIGA_USD_BRL_RATE = $Rate
        return
    }

    if (Test-Path $cfgPath) {
        $line = Get-Content $cfgPath | Where-Object { $_ -match "^\s*USD_BRL_RATE\s*=" } | Select-Object -First 1
        if ($line) {
            $value = ($line -split "=", 2)[1].Trim()
            Write-Step "    Taxa USD->BRL via scanner.config: $value" "Green"
            $env:LIGA_USD_BRL_RATE = $value
            return
        }
    }

    Write-Step "    Sem scanner.config nem -Rate; usando fallback do Python (5.20)." "Yellow"
}

function Invoke-Scanner {
    Write-Step "[3/3] Rodando scanner..."
    $main = Join-Path $root "src\main.py"
    if (-not (Test-Path $main)) {
        # No Linux/Mac o separador e diferente
        $main = Join-Path $root "src/main.py"
    }
    & $venvPython $main 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: scanner falhou (exit $LASTEXITCODE)." "Red"
        throw "Scanner falhou."
    }
    Write-Step "    Scanner concluido. Relatorios em reports/." "Green"
}

try {
    Write-Step "==> Scanner liga-pokemon (log: $logFile)"
    Assert-Venv
    Read-Config
    Invoke-Scanner
    Write-Step "==> Concluido." "Green"
} catch {
    Write-Step "==> ERRO: $($_.Exception.Message)" "Red"
} finally {
    Read-Host "Pressione Enter para sair..."
}
