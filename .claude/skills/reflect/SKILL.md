---
name: reflect
description: >-
  Retrospectiva de sessão — varre o que aconteceu em 4 baldes (preferência da
  Eli, decisão, atrito técnico, quick win), confere o que já está escrito,
  MOSTRA antes de salvar e só então grava. Destino: preferências vão pra
  `## Sobre a Eli` e decisões pra `## Decisões` do CLAUDE.md; atrito técnico
  vira armadilha numerada no CLAUDE.md (+ issue/PR no `scanners-commons` se
  afetar mais de um scanner); quick win é aplicado direto na branch. Use no fim
  de uma sessão, depois de um bug chato, quando a Eli corrigir seu rumo, ou
  quando ela pedir "reflete", "o que aprendemos", "salva isso".
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion, WebFetch, mcp__github__get_file_contents, mcp__github__issue_write, mcp__github__search_issues, mcp__github__create_pull_request, mcp__github__push_files, mcp__github__list_pull_requests
---

# `/reflect` — retrospectiva que vira documento, não conversa

Você foi acionado pelo **`/reflect`**. Seu trabalho é transformar o que esta
sessão ensinou em **artefato durável no lugar certo** — e nada mais. Você não
está resolvendo a tarefa da sessão (isso é o `/auto`); está fechando o ciclo
dela.

**Foco da rodada (se houver):** `$ARGUMENTS` — quando vazio, varre a sessão
inteira.

**Por que este skill existe nos dois lugares, gravando coisas diferentes:** no
ambiente do chat/Cowork o `/reflect` grava na **memória**; aqui, num repo, a
memória não viaja (sessão de nuvem nasce sem ela). Então aqui o destino é
**`CLAUDE.md` + `scanners-commons`** — os únicos portadores de regra que
sobrevivem à próxima sessão. Mesmo ritual, destino que faz sentido no meio.

**O ritual, em ordem, sem pular etapa:**
varredura em 4 baldes (§1) → checar o que já existe (§2) → **mostrar antes de
salvar** (§3) → escrever (§4).

---

## 0. Pré-voo (obrigatório — dispare em PARALELO)

1. **Leia o `CLAUDE.md` do repo** — inteiro. Sem ele você não sabe o que já está
   documentado e vai duplicar regra existente (o erro nº 1 deste skill).
2. **Confirme a branch designada** (`claude/…` do system prompt). Quick win vai
   pra ela; **nunca** direto na `main` (regra da frota).
3. **Cheque o estado do git**: `git status --short` e `git log --oneline -5`.
   Trabalho não commitado muda o que você pode aplicar como quick win.
4. **Releia a sessão** (ou o handoff, se existir): onde a Eli te corrigiu, onde
   você travou, onde algo pareceu verde e estava vazio, o que ela decidiu.

---

## 1. Varredura em 4 baldes

Passe a sessão pelos 4 baldes. O **teste de pertencimento** é o que decide o
balde — não o assunto.

| # | Balde | Teste de pertencimento | Destino |
|---|---|---|---|
| 1 | **Preferência da Eli** | é sobre **como conversar/entregar** — tom, formato, cadência, o que a irrita. Vale na próxima sessão seja qual for a tarefa. | `## Sobre a Eli` no `CLAUDE.md` |
| 2 | **Decisão** | é martelo batido sobre **o que o scanner faz** — regra de negócio, threshold, escopo, piso. Muda comportamento ou critério. | `## Decisões` no `CLAUDE.md` |
| 3 | **Atrito técnico** | **custou tempo**: algo quebrou, mentiu ou enganou. Tem sintoma → causa → fix. | armadilha numerada no `CLAUDE.md` (+ `scanners-commons` se cross-scanner, §4d) |
| 4 | **Quick win** | correção **pequena e reversível** que impede o atrito de voltar: teste que falha, guard, erro honesto. | código na **branch designada** |

Regras da varredura:

- **Balde 3 e 4 andam em par.** Todo atrito técnico pergunta: "que teste teria
  pego isso?". Se a resposta é barata, virou quick win. Se é cara, vira linha de
  pendência no resumo (§7) — **não** um TODO inventado no código.
- **Não force volume.** Sessão sem aprendizado real → diga "nada novo" e pare.
  Inventar item pra parecer produtivo é a mesma desonestidade de inventar preço.
- **Priorize o que muda comportamento futuro.** 3 itens que a próxima sessão vai
  usar valem mais que 12 observações.
- **Cada item precisa de evidência**: o que a Eli disse, ou o que aconteceu na
  sessão. Item sem evidência não entra — você **nunca** infere uma preferência
  ou decisão que ela não expressou.

---

## 2. Checar o que já existe (antes de escrever qualquer coisa)

Duplicata é pior que ausência: o `CLAUDE.md` vira ruído e a próxima sessão não
sabe qual linha manda. Para **cada** item, procure antes:

```bash
grep -n -i "<palavra-chave do item>" CLAUDE.md
grep -n "armadilha nº" CLAUDE.md          # numeração vigente das armadilhas
```

Classifique em 1 dos 4 veredictos:

| Veredito | Quando | O que fazer |
|---|---|---|
| **NOVO** | nada no doc cobre isso | escreve (após o gate do §3) |
| **JÁ EXISTE** | o doc já diz isso | **descarta em silêncio** — não reescreve com outras palavras |
| **ATUALIZA** | o doc diz algo desatualizado/parcial | edita a linha existente; **não** adiciona uma segunda |
| **CONTRADIZ** | o novo item conflita com regra vigente | **PARA e pergunta** (`AskUserQuestion`) — regra vigente só cai por decisão explícita da Eli |

O `CONTRADIZ` é freio duro. Exemplo real: se a sessão sugerir margem de 25%, isso
**não** é um item de reflect — é um conflito com o invariante de 30% da frota, e
só a Eli derruba.

---

## 3. Mostrar antes de salvar (gate — não negociável)

**Nada dos baldes 1, 2 e 3 é escrito antes de a Eli ver o texto exato.** Estes
destinos (`CLAUDE.md`, `scanners-commons`) viram regra pra toda sessão futura —
regra errada gravada é cara de descobrir e cara de tirar. Este é o ponto onde o
`/reflect` **diverge do `/auto`**: aqui o default não é "decide e executa".

**O balde 4 (quick win) é a exceção:** é código, na branch, reversível e coberto
por teste — aplique direto e relate, exatamente como o `/auto` faria.

Formato da prévia no chat:

```
## 🪞 Reflect — <data> — <n> itens

| # | Balde | Item (1 linha) | Destino | Veredito |
|---|---|---|---|---|
| 1 | Preferência | ... | CLAUDE.md § Sobre a Eli | NOVO |
| 2 | Atrito | ... | CLAUDE.md § Coletor ao vivo (armadilha nº 4) | NOVO |
| 3 | Quick win | ... | branch (APLICADO) | — |

<o texto LITERAL de cada linha que vai entrar, em bloco, um por destino>
```

Depois da prévia, pergunte **uma vez** (`AskUserQuestion`) o que corta. Sem
resposta = não escreve. Nunca grave "porque é obviamente certo".

---

## 4. Escrever (destino por destino)

### 4a. `## Sobre a Eli` (preferências)

- Fica **logo após o bloco de intro**, antes de `## 🛰️ Convenções da frota` —
  é o que qualquer sessão precisa ler primeiro.
- **A seção pode não existir ainda**: crie-a, não invente outro nome nem
  pendure a preferência numa seção técnica.
- Uma linha por preferência, no imperativo, com a data: como ela quer, não uma
  narrativa de como você descobriu.
  `- **Entrega sem preâmbulo** — ir direto à tabela/resposta; contexto só se ela pedir. (2026-09-12)`

### 4b. `## Decisões` (martelos batidos)

- Fica **imediatamente antes de `## Estado, pendências e histórico`** — é
  normativo, e é onde a próxima sessão procura "isso já foi decidido?".
- Formato: **decisão + data + motivo em meia linha**. O motivo é o que impede a
  próxima sessão de "consertar" a decisão achando que é bug:
  `- **Selados não têm piso de preço** (2026-06-27) — piso de R$50 é relevância de single; em selado o único critério é margem ≥30%.`
- Decisão que tem seção própria (piso, margem, entrega) vira **link pra seção**,
  não cópia: fonte única, sempre.

### 4c. Armadilha numerada (atrito técnico)

- Vai na **seção do componente afetado** (ex.: `## Coletor ao vivo
  (src/collectors/liga_live.py)`), não numa lista solta no fim.
- **Numeração é contínua dentro da seção** — confira a maior existente com
  `grep -n "armadilha nº" CLAUDE.md` e use a próxima.
- Formato vigente do repo (mantenha, não invente outro):
  `- **<título curto>** (armadilha nº N, fix #PR): <o que parecia> — <o que era> — <o que fazer>.`
- A armadilha tem que responder **"como eu detecto isso na próxima vez?"**.
  Sintoma sem detecção não previne nada.

### 4d. `scanners-commons` (só quando é cross-scanner)

**Teste do cross-scanner** — vale pro commons se **qualquer uma** for verdade:

- a causa mora em algo **compartilhado**: convenção da frota, fonte de preço,
  manejo de segredo, fluxo git, formato de entrega, câmbio;
- o **mesmo sintoma reproduziria** em outro repo da frota (CardTrader, MYP,
  COMC, eBay, sealed, integrated);
- é uma nova instância de uma das **3 famílias de erro** do manual.

Caso contrário é local — para no `CLAUDE.md` deste repo.

Como registrar:

1. **Issue** para atrito/armadilha nova; **PR** quando o texto do manual em si
   precisa mudar.
2. Repo privado `matheuscllm-lgtm/scanners-commons` — em sessão de nuvem ele
   **não está no escopo GitHub por padrão**: anexe com `add_repo`
   (`owner=matheuscllm-lgtm`, `repo=scanners-commons`) antes de tentar.
3. **Sem acesso → não fabrique sucesso.** Cole no chat o issue pronto pra colar
   e aponte a cópia-mestra local `C:\Users\mathe\scanners-commons\`. Dizer
   "registrei no commons" sem ter registrado é o mesmo pecado de afirmar CI
   verde sem rodar.
4. **Nunca** coloque dado de scan (preço, carta, URL de oferta) no issue/PR —
   `DELIVERY_CHAT.md`: resultado é só no chat, GitHub guarda código e doc.
5. Cheque duplicata antes (`mcp__github__search_issues`) — o commons é
   compartilhado pela frota inteira.

### 4e. Quick win (código, direto na branch)

1. **Primeiro o teste que falha.** Escreva o teste que pega o atrito e veja-o
   falhar **antes** do fix — teste que nasce verde não prova nada.
2. Aplique o guard/fix mínimo. **Nunca** "conserte" pulando, marcando skip ou
   afrouxando teste.
3. Rode a suíte e **cole a saída real** (`python -m pytest -q`). Falhou? relate
   falhado; não maquie.
4. **Commit atômico por quick win**, mensagem ligando ao atrito
   (`test(liga-live): guard de listagem sem cartas — armadilha nº 4`).
5. Push na branch designada + PR draft (cheque se já existe antes de criar).

---

## 5. Exemplo de referência — o caso do `edid` (#39)

O caso que define o padrão. **Entrada:** um scan ao vivo voltou 0 cartas, sem
erro nenhum. Parecia carta sem oferta; era a Liga ter mudado o roteamento — a
URL de listagem passou a exigir o `edid` numérico e a URL antiga caía na home
**sem cartas**, silenciosamente.

Saída do `/reflect` nos 4 baldes:

| Balde | Item | Destino |
|---|---|---|
| 1 — Preferência | *(nada — não houve preferência nova)* | — |
| 2 — Decisão | *(nada — não mudou regra de negócio)* | — |
| 3 — Atrito | roteamento da Liga mudou; listagem sem `edid` cai na home sem cartas | armadilha nº 3 em `## Coletor ao vivo` |
| 3b — Cross? | **SIM** — "coleta verde mas vazia" é a família de erro nº 1 da frota, com causa nova (roteamento da fonte, não BOM em chave) | issue no `scanners-commons` |
| 4 — Quick win | `TestParseEditions` + `TestListingUrl` em `tests/test_liga_live.py`; erro explícito quando a página de edições carrega e **nenhum** `edid` aparece | branch + PR #39 |

O texto que foi pro `CLAUDE.md` (formato a copiar):

```markdown
- **URL de listagem exige `edid`** (armadilha nº 3, fix #39): a Liga mudou o
  roteamento (2026-06) e a URL de listagem passou a **exigir o `edid` numérico**
  além do código do set — a URL antiga (`?view=cards/search&card=ed=CODE`) cai
  na home SEM cartas. O coletor extrai o mapa `{CODIGO: edid}` da página de
  edições e monta a URL com os dois.
```

Repare no que faz esse registro funcionar e replique: **sintoma primeiro** ("cai
na home SEM cartas" — o que você vai ver), causa depois, fix por último, com o
PR linkado. E o quick win não foi "arrumar a URL" (isso era a tarefa); foi o
**erro explícito quando nenhum `edid` aparece** — o que impede a próxima mudança
de roteamento de voltar como silêncio.

---

## 6. Invariantes que o `/reflect` NUNCA quebra

- **Nunca inventa preferência ou decisão** que a Eli não expressou. Sem
  evidência na sessão, não existe. (Mesma régua do "nunca inventar preço".)
- **Nunca escreve nos baldes 1–3 sem o gate do §3.**
- **Nunca apaga nem reescreve regra vigente** por conta própria — `CONTRADIZ`
  vira pergunta (§2).
- **Nunca põe dado de scan** (preço, carta, oferta, log de coleta) no
  `CLAUDE.md`, em issue ou em PR — `DELIVERY_CHAT.md`.
- **Nunca commita segredo**; chave com BOM/zero-width é a família de erro nº 1.
- **Nunca push direto na `main`** — branch designada + PR draft.
- **Nunca afirma ter registrado** algo que não registrou (issue no commons,
  teste rodado, CI verde). Falta de acesso se declara, não se contorna.
- **Nunca recomenda compra** — aqui também: capital é da operadora.

---

## 7. Encerramento (obrigatório)

Termine sempre com um resumo curto e honesto:

- **o que foi gravado**, por destino (§ do `CLAUDE.md`, issue/PR do commons,
  commit da branch) — com link/linha quando houver;
- **o que foi descartado** e por quê (`JÁ EXISTE` / sem evidência);
- **quick wins aplicados** + saída real do teste;
- **o que ficou pendente** (atrito caro demais pra quick win, item que precisa
  de decisão da Eli, commons sem acesso);
- se não houve nada: diga **"nada novo nesta sessão"** — é resultado válido.
