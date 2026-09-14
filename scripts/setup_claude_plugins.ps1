# setup_claude_plugins.ps1 — instala, UMA VEZ, o setup global do Claude Code no PC do operador.
# Escopo: user (default do CLI) => vale em TODOS os repos. Nao usa --scope de proposito.
# Fonte da lista: reel @99hud (2026-08-05) + decisao do operador (CLAUDE.md, secao Plugins).
# Comandos validados em sessao remota em 2026-09-14 (Claude Code 2.1.270).
$ErrorActionPreference = "Continue"

Write-Host "== 1/4 marketplaces-fonte ==" -ForegroundColor Cyan
claude plugin marketplace add anthropics/claude-plugins-official   # claude-code-setup (oficial)
claude plugin marketplace add thedotmack/claude-mem                # claude-mem
claude plugin marketplace add kingbootoshi/cartographer            # cartographer

Write-Host "== 2/4 plugins (scope user) ==" -ForegroundColor Cyan
claude plugin install claude-code-setup@claude-plugins-official
claude plugin install claude-mem@thedotmack
claude plugin install cartographer@cartographer-marketplace
claude plugin list

Write-Host "== 3/4 Headroom (proxy local de compressao; NAO e plugin, e pacote Python) ==" -ForegroundColor Cyan
# Requer Python 3.11+ no PATH. Roda 100% local; nao precisa de conta nem de cartao.
python -m pip install --upgrade "headroom-ai[proxy]"
headroom --version
# Uso diario (substitui `claude`): headroom wrap claude
# Com OmniRoute (OMNIROUTE.md): o Headroom fica na frente e repassa pro gateway ->
#   $env:ANTHROPIC_TARGET_API_URL = "http://127.0.0.1:20128"; headroom wrap claude

Write-Host "== 4/4 Task Observer (skill, NAO plugin) ==" -ForegroundColor Cyan
Write-Host "Task Observer nao se instala por CLI. Faca upload do bundle task-observer.skill em"
Write-Host "claude.ai > Settings > Capabilities > Skills — a skill sincroniza sozinha para o Cowork e"
Write-Host "para o Claude Code (pasta ~/.claude/skills/synced/). Depois cole o bloco de ativacao"
Write-Host "(CLAUDE.md, secao Plugins) nas preferencias pessoais do claude.ai. Detalhes: CLAUDE.md."
Write-Host "Feito. Reabra o Claude Code (ou /reload-plugins) para carregar os plugins." -ForegroundColor Green
