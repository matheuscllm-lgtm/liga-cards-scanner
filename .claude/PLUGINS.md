# Plugins do Claude Code — liga-cards-scanner

Config declarativa em [`.claude/settings.json`](settings.json). Qualquer sessão que
abrir este repo **e confiar na pasta** recebe os três plugins automaticamente.

## O que está declarado

| Plugin | Marketplace (repo) | Origem | O que traz |
|---|---|---|---|
| `claude-code-setup` | `anthropics/claude-plugins-official` | **Anthropic (oficial)** | 1 skill `claude-automation-recommender` — analisa o codebase e sugere hooks/skills/MCP/subagents sob medida |
| `claude-mem` | `thedotmack/claude-mem` | terceiro | memória persistente entre sessões: 20 skills, 6 hooks, 1 MCP (`mcp-search`) |
| `cartographer` | `kingbootoshi/cartographer` | terceiro | 1 skill que mapeia o codebase com subagents em paralelo → `docs/CODEBASE_MAP.md` |

## Instalação manual (PC do operador — Windows)

O `.claude/settings.json` só aplica **depois de confiar na pasta** (prompt de
workspace trust na primeira abertura). Para instalar direto, sem depender disso:

```powershell
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add thedotmack/claude-mem
claude plugin marketplace add kingbootoshi/cartographer

claude plugin install claude-code-setup@claude-plugins-official
claude plugin install claude-mem@thedotmack
claude plugin install cartographer@cartographer-marketplace
```

Conferir com `claude plugin list` e `claude plugin details <nome>`.

## Ressalvas (leia antes de usar em scan longo)

- **`claude-mem` é o caro dos três.** ~2.000 tokens *always-on* em toda sessão +
  hook `PostToolUse` disparando um worker node a cada chamada de ferramenta. Num
  scan ao vivo da Liga (centenas de páginas, Chrome headful) isso pesa. Se
  atrapalhar: `claude plugin disable claude-mem`.
- **`claude-mem` precisa de disco persistente** (`~/.claude-mem`) e de `node` no
  PATH. Em sessão remota (container efêmero) a memória morre junto com o
  container — o valor dele está no PC do operador, não na nuvem.
- **Dois são de terceiros** (`thedotmack`, `kingbootoshi`) e registram hooks que
  executam comandos locais. Atualização via `claude plugin update <nome>` puxa
  código novo desses repos — atualize de forma consciente.
- **`cartographer` gasta tokens de verdade**: dispara subagents em paralelo sobre
  o codebase inteiro. Rode sob demanda, não em loop.
