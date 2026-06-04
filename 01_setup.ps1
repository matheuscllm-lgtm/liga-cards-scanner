<#
.SYNOPSIS
Setup do liga-pokemon-scanner. Cria .venv e instala dependencias.

.DESCRIPTION
Padrao MyP: duplo-clique no .bat correspondente (ou rodar via
.\01_setup.ps1). Encontra Python 3.10+ no Windows preferindo o Python
Launcher 'py'. Forca UTF-8 no console e nas chamadas Python. Loga em
logs/setup_<timestamp>.log via Tee-Object.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

# Forca UTF-8 no console e no Python para evitar mojibake em nomes de cards
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logsDir "setup_$stamp.log"

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

function Find-Python {
    Write-Step "[1/4] Procurando Python 3.10+ no sistema..."

    $candidates = @()

    if ($isWin) {
        # Prioridade: Python Launcher do Windows (mais confiavel que 'python',
        # que pode apontar para o stub da Microsoft Store).
        $candidates += "C:\Windows\py.exe"
        $candidates += "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
        $candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        $candidates += "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
        $candidates += "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
        $candidates += "$env:ProgramFiles\Python313\python.exe"
        $candidates += "$env:ProgramFiles\Python312\python.exe"
        $candidates += "$env:ProgramFiles\Python311\python.exe"
        $candidates += "$env:ProgramFiles\Python310\python.exe"
    }

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            $version = & $path --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$version" -match "Python 3\.(1[0-9]|[2-9][0-9])") {
                Write-Step "    Python encontrado: $path ($version)" "Green"
                return $path
            }
        }
    }

    foreach ($name in @("py", "python3", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $cmd) { continue }
        # Filtra o stub da Microsoft Store, que mora em WindowsApps
        if ($isWin -and ($cmd.Source -like "*WindowsApps*")) { continue }
        $version = & $name --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$version" -match "Python 3\.(1[0-9]|[2-9][0-9])") {
            Write-Step "    Python encontrado: $($cmd.Source) ($version)" "Green"
            return $cmd.Source
        }
    }

    Write-Step "    ERRO: Python 3.10+ nao encontrado." "Red"
    Write-Step "    Instale em https://www.python.org/downloads/ e marque 'Add to PATH'." "Yellow"
    throw "Python 3.10+ nao encontrado."
}

function New-Venv {
    param([string]$SysPython)
    if (Test-Path $venv) {
        Write-Step "[2/4] .venv ja existe em $venv, pulando criacao." "Yellow"
        return
    }
    Write-Step "[2/4] Criando .venv em $venv..."
    & $SysPython -m venv $venv 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: falha ao criar .venv." "Red"
        throw "Falha ao criar venv (exit $LASTEXITCODE)."
    }
    Write-Step "    .venv criado." "Green"
}

function Update-Pip {
    Write-Step "[3/4] Atualizando pip..."
    & $venvPython -m pip install --upgrade pip 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: falha ao atualizar pip." "Red"
        throw "Falha ao atualizar pip (exit $LASTEXITCODE)."
    }
    Write-Step "    pip atualizado." "Green"
}

function Install-Requirements {
    Write-Step "[4/4] Instalando requirements.txt + pytest..."
    $reqs = Join-Path $root "requirements.txt"
    & $venvPython -m pip install -r $reqs 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: falha ao instalar requirements.txt." "Red"
        throw "Falha em pip install -r requirements.txt (exit $LASTEXITCODE)."
    }
    & $venvPython -m pip install pytest 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Step "    ERRO: falha ao instalar pytest." "Red"
        throw "Falha em pip install pytest (exit $LASTEXITCODE)."
    }
    Write-Step "    Dependencias instaladas." "Green"
}

try {
    Write-Step "==> Setup do liga-pokemon-scanner (log: $logFile)"
    $sys = Find-Python
    New-Venv -SysPython $sys
    Update-Pip
    Install-Requirements
    Write-Step "==> Setup concluido. Use .\02_scan_liga.ps1 para rodar o scanner." "Green"
} catch {
    Write-Step "==> ERRO: $($_.Exception.Message)" "Red"
} finally {
    Read-Host "Pressione Enter para sair..."
}
