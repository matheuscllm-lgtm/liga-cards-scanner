# Checklist manual — tornar o repositório público (discreto)

> Tudo que o Claude **não** consegue fazer por você (mudanças de configuração no
> site do GitHub). Faça **nesta ordem**. O objetivo é reduzir descoberta casual —
> **não** é segurança real: qualquer pessoa com o link verá tudo, e o código
> continua achável por busca de código. O scrub do README é cosmético.
>
> ⚠️ **Antes de virar público:** confirme que o PR de preparação já foi mergeado
> no `main` (ele tira o doc de handoff do repositório e neutraliza o README).

## 0. Pré-checagem (1 min)

- [ ] O PR `chore/prepare-public-release` está **mergeado** no `main`.
- [ ] Os branches remotos abaixo **não existem mais**. O Claude **não** apaga
      branches remotos — rode você no seu terminal:
      ```bash
      git push origin --delete claude/self-evolving-agent-integration-budf77
      ```
      (Confira a lista atual com `git ls-remote --heads origin`; mantenha só
      `main`.)

## 1. Renomear o repositório (nome menos óbvio)

- [ ] `Settings → General → Repository name` → trocar `Liga-cards-scanner`
      por algo neutro, ex.: `price-compare-tool` ou `pc-utils`.
- [ ] (O GitHub cria redirect do nome antigo; se quiser cortar isso, evite usar
      o nome antigo em links públicos.)
- [ ] Atualizar o `git remote` local depois:
      ```bash
      git remote set-url origin https://github.com/matheuscllm-lgtm/<novo-nome>.git
      ```

## 2. Remover description e topics

- [ ] Na página inicial do repo → engrenagem ⚙️ ao lado de "About".
- [ ] Apagar a **Description**.
- [ ] Apagar todos os **Topics** (tags).
- [ ] Desmarcar "Use your GitHub Pages website" e "Releases/Packages" se marcados.

## 3. Desligar features que criam superfície pública

- [ ] `Settings → General → Features`:
  - [ ] **Issues** → desligar.
  - [ ] **Wikis** → desligar.
  - [ ] **Discussions** → desligar.
  - [ ] **Projects** → desligar.
- [ ] `Settings → Pages` → Source = **None** (confirmar que Pages está desligado).

## 4. Conferir secrets de CI (antes de publicar)

- [ ] Este projeto **não usa nenhum secret** para rodar (default mock + caminho
      ao vivo só precisam de uma taxa numérica). O workflow de testes roda sem
      secret algum.
- [ ] Lembre: em repo **público**, os **logs e artifacts** de cada run dos
      workflows ficam baixáveis por qualquer um que achar o repo. Para
      resultados realmente privados, rode o scan **local** (venv + Chrome
      headful), nunca no Actions.

## 5. Tornar público

- [ ] `Settings → General → Danger Zone → Change repository visibility`
      → **Make public** → confirmar digitando o nome.

## 6. Validar que o Actions roda de graça

- [ ] Aba **Actions** → workflow **tests** deve rodar sozinho no próximo push/PR
      (ou rode via "Run workflow") e ficar **verde**, em runner `ubuntu-latest`.
- [ ] `Settings → Billing` → confirmar que minutos de Actions de repo público
      **não** consomem cota paga (são gratuitos).

## 7. Pós-publicação (higiene)

- [ ] Conferir a aba **Actions → artifacts** e apagar artifacts antigos que
      tenham ficado de runs anteriores (eles podem conter dados de deal).
