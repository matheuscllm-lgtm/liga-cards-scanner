# OmniRoute — fallback de modelo quando o limite acaba

Procedimento verificado (2026-09-12) para ligar o **Claude Code** a um gateway
[OmniRoute](https://www.omniroute.online/) local, de modo que, **quando a cota
de um modelo estoura, o gateway troca para o próximo da cadeia sozinho** em vez
de a sessão parar.

> Esta página é **manual de ambiente do operador**, não faz parte do pipeline do
> scanner. Nada aqui muda scan, margem, piso ou entrega — o scanner continua
> sendo Python puro, sem nenhuma chamada a LLM.

## O que o OmniRoute resolve

O OmniRoute é um gateway local (porta padrão `20128`) que expõe um endpoint
compatível com a Messages API da Anthropic e roteia cada chamada por um
**combo**: uma cadeia ordenada de alvos. A cadeia padrão dele é de 4 camadas —
**Assinatura → API Key → modelo barato → modelo grátis**. Quando a cota, o rate
limit ou a saúde do alvo atual falha, ele avança para o próximo sem intervenção.

Do lado do Claude Code isso é só ambiente: `ANTHROPIC_BASE_URL` passa a apontar
para o gateway em vez de `api.anthropic.com`.

## Instalação (máquina do operador)

```bash
# npm (caminho mais curto)
npm install -g omniroute
omniroute                      # sobe o gateway + dashboard em http://localhost:20128

# ou Docker
docker run -d --name omniroute --restart unless-stopped \
  -p 127.0.0.1:20128:20128 -v omniroute-data:/app/data \
  diegosouzapw/omniroute:latest
```

No dashboard (`http://localhost:20128`):

1. **Providers** — conecte as contas/chaves que vão compor a cadeia.
2. **Combos** (`/dashboard/combos`) — monte a cadeia na ordem que você quer
   gastar. Estratégias disponíveis: `priority` (ordem fixa, avança ao falhar),
   `cost-optimized` (mais barato disponível) e `headroom` (quem tem mais cota
   sobrando). Para o caso "quando o limite acaba, troca de modelo", `priority`
   é a que corresponde ao pedido.
3. **Endpoints** — gere o token de acesso (`oma_live_...`).

## Ligar o Claude Code

O jeito suportado é o comando do próprio OmniRoute — ele normaliza a URL,
faz health-check e injeta as credenciais:

```bash
omniroute launch                                   # gateway local
omniroute launch --profile <nome>                  # perfil nomeado
omniroute launch --remote http://IP:20128 --api-key oma_live_xxx
omniroute setup-claude                             # grava ~/.claude/profiles/<nome>/settings.json
```

Equivalente manual (quando você quer controlar as variáveis):

| Variável | Valor |
|---|---|
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:20128` — **raiz do gateway, sem `/v1`** |
| `ANTHROPIC_AUTH_TOKEN` | o token `oma_live_...` do dashboard |
| `ANTHROPIC_MODEL` | opcional; combo a forçar, ex. `claude/combo/custo-otimizado` |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` | `1` para o `/model` listar os modelos do gateway |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | opcional; janela real do modelo não-Claude |

## Gotchas (os que custam tempo)

1. **Nada de `/v1` na base URL.** O dashboard mostra `http://localhost:20128/v1`
   (endpoint OpenAI-compatível), mas o Claude Code concatena `/v1/messages`
   sozinho — colar com `/v1` vira `/v1/v1/messages` → 404, e o sintoma é
   "o gateway está sendo ignorado".
2. **As variáveis são lidas no startup.** Mudou env? Reinicie o Claude Code.
3. **`400 Ambiguous model`** aparece quando o mesmo ID de modelo existe em dois
   providers. Prefixe (`cc/claude-opus-4-8`) ou ligue o toggle "Prefer Claude
   Code for unprefixed Claude models".
4. **Janela de contexto.** Modelo não-Claude é assumido com 200k; se a janela
   real for menor, ajuste `CLAUDE_CODE_AUTO_COMPACT_WINDOW` para abaixo dela,
   senão o auto-compact dispara tarde e a chamada estoura.
5. **Perfis não guardam token** — use `omniroute launch --profile <nome>` ou
   exporte `ANTHROPIC_AUTH_TOKEN` na hora.

## Decisões deste repositório

- **Não existe `.claude/settings.json` versionado aqui, e não deve existir com
  essas variáveis.** Settings de projeto valem também para as sessões do Claude
  Code na nuvem, que não enxergam `127.0.0.1:20128` — apontar o repo para um
  gateway local quebraria toda sessão remota. O ambiente entra **no shell que
  abre o Claude Code**, não no repositório.
- **Token nunca versionado.** Ele vive no dashboard/OmniRoute ou numa variável
  de ambiente local — mesma regra da `POKEMONTCG_API_KEY`. Se for guardar em
  arquivo, use um caminho já ignorado (`.env`) e salve **sem BOM** (o erro
  recorrente nº 1 da frota: BOM na chave derruba o header).
- **Reverter é fechar o shell.** Sem as variáveis, o Claude Code volta a falar
  direto com `api.anthropic.com`.

## O que você está aceitando ao ligar isso

- **Seu código e seus prompts passam a transitar pelo provedor do fallback.**
  Enquanto a cadeia estiver na Anthropic, nada muda; quando ela cair para um
  modelo de terceiro, o conteúdo da sessão vai para aquele provedor.
- **Credencial de assinatura em gateway de terceiro** pode conflitar com os
  termos de uso do plano. A camada segura da cadeia é API key própria (sua ou
  do provedor alternativo), não a credencial da assinatura.
- **Modelo não-Claude dentro do Claude Code** muda qualidade e compatibilidade
  de ferramentas — trate os degraus baixos da cadeia como plano B real, não
  como equivalente.
