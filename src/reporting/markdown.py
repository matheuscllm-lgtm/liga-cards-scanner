"""Gerador da tabela markdown de ENTREGA (a saida canonica do scanner).

O resultado de um scan da Liga e entregue ao operador como tabela markdown
no chat (terminal ou app) — NUNCA como arquivo .xlsx/.csv por padrao (regra
cross-scanner do operador, 2026-06-06). Esta tabela e a fonte unica de
verdade da entrega: ela NUNCA deve ser montada a mao.

Formato canonico da frota (2026-07-02): espelho do bucket limpo do
`myp_summary.py` (repo myp-arbitrage-scanner), em 3 buckets:

- 🟢 Aprovados (match exato)
- ⚠️ Aprovados com match fuzzy — "validar manualmente" (caveat na SECAO,
  padrao MYP; coluna extra `Match` com o score)
- ❌ Reprovados (margem < minima ou preco < piso) — mantem o invariante da
  frota de mostrar TODAS as linhas, nao amostra curada

Colunas (identicas ao MYP, adaptadas a Liga):

    | # | Margem % | Liga R$ | TCG US$ | Dif | Carta | Set | Raridade |
    | Cond | Qtd | Links |

- **Carta**: nome + numero SEM `#` (ex. ``Umbreon ex 161``), estilo MYP.
- **Dif**: lucro bruto em R$ (`TCG R$ − Liga R$`).
- **Raridade** / **Qtd**: `—` (a Liga nao expoe raridade nem estoque).
- **Cond**: `NM` literal (invariante NM-only do coletor).
- **Links**: ``[oferta](url) · [TCG](url)`` — clicaveis, SEMPRE os dois
  lados quando existirem (oferta na Liga + referencia TCGplayer).

Piso de preco (R$50) e um filtro de relevancia que vale SO para cartas
avulsas — produtos selados NAO tem piso (e nem sao escopo deste scanner;
selados moram no repo sealed-scanner).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita import circular em runtime
    from src.matching.card_matcher import Comparison

# Abaixo disto, o match e fuzzy o suficiente p/ pedir conferencia manual.
SUSPECT_MATCH_SCORE = 1.0

_HEADER = (
    "| # | Margem % | Liga R$ | TCG US$ | Dif | Carta | Set | "
    "Raridade | Cond | Qtd | Links |"
)
_SEP = "|---|---:|---:|---:|---:|---|---|---|---|---:|---|"
_HEADER_MATCH = _HEADER + " Match |"
_SEP_MATCH = _SEP + "---:|"


def fmt_brl(v: float | None) -> str:
    """Formata valor BRL pra display (R$1.234,56). '—' se ausente.

    Truque de replace portado do myp_summary.py — independe de locale
    (locale.setlocale quebraria no CI ubuntu)."""
    if v is None:
        return "—"
    try:
        return f"R${float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "—"


def fmt_usd(v: float | None) -> str:
    """Formata valor USD pra display (US$1,234.56). '—' se ausente."""
    if v is None:
        return "—"
    try:
        return f"US${float(v):,.2f}"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(v: float | None) -> str:
    """Formata margem pra display (95.0%). '—' se ausente.

    ATENCAO: `Comparison.margin_percent` JA E percentual (95.0) — diferente
    do MYP, onde a margem e fracao e o fmt_pct multiplica por 100. NAO
    adicionar `*100` aqui (inflaria a margem 100x)."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}%"
    except (ValueError, TypeError):
        return "—"


def carta_label(name: str, number: str = "") -> str:
    """Coluna `Carta` = nome + numero numa string so ('Umbreon ex 161').

    Estilo MYP: sem `#`. Se o numero ja esta contido no nome, nao duplica."""
    name = (name or "").strip()
    num = (number or "").strip()
    if num and num not in name:
        return f"{name} {num}"
    return name


def _links(c: "Comparison") -> str:
    """Celula de links clicaveis: oferta na Liga + referencia TCGplayer.

    Formato canonico cross-scanner: `[oferta](url) · [TCG](url)`. Emite so
    os links que existirem; '—' se nenhum. NUNCA inventa URL."""
    parts = []
    if c.liga_url:
        parts.append(f"[oferta]({c.liga_url})")
    if c.tcg_url:
        parts.append(f"[TCG]({c.tcg_url})")
    return " · ".join(parts) if parts else "—"


def _escape(text: str) -> str:
    """Neutraliza o pipe pra nao quebrar a coluna do markdown."""
    return text.replace("|", "\\|")


def _row(idx: int, c: "Comparison", *, bold_margin: bool,
         with_match: bool) -> str:
    margin = fmt_pct(c.margin_percent)
    if bold_margin:
        margin = f"**{margin}**"
    cells = [
        str(idx),
        margin,
        fmt_brl(c.price_liga_brl),
        fmt_usd(c.price_tcg_usd),
        fmt_brl(c.price_tcg_brl - c.price_liga_brl),
        _escape(carta_label(c.card_name, c.card_number)),
        _escape(c.set_name),
        "—",   # Raridade: a Liga nao expoe
        "NM",  # invariante NM-only
        "—",   # Qtd: a Liga nao expoe estoque por oferta
        _links(c),
    ]
    if with_match:
        cells.append(f"{c.match_score:.2f}")
    return "| " + " | ".join(cells) + " |"


def _bucket(rows: list["Comparison"], *, bold_margin: bool,
            with_match: bool) -> list[str]:
    lines = [_HEADER_MATCH if with_match else _HEADER,
             _SEP_MATCH if with_match else _SEP]
    for i, c in enumerate(rows, 1):
        lines.append(_row(i, c, bold_margin=bold_margin,
                          with_match=with_match))
    return lines


def build_markdown(items: list["Comparison"], rate: float) -> str:
    """Monta a tabela markdown de entrega (string pronta pra imprimir)."""
    from src.pricing.margin import MIN_MARGIN_PERCENT, MIN_PRICE_BRL

    approved = [c for c in items if c.status == "approved"]
    clean = [c for c in approved if c.match_score >= SUSPECT_MATCH_SCORE]
    fuzzy = [c for c in approved if c.match_score < SUSPECT_MATCH_SCORE]
    rejected = [c for c in items if c.status != "approved"]

    lines: list[str] = []
    lines.append(
        f"**Liga Pokémon — {len(items)} ofertas comparadas, "
        f"{len(approved)} aprovadas** "
        f"(margem bruta ≥ {MIN_MARGIN_PERCENT:.0f}% e piso R${MIN_PRICE_BRL:.0f} — "
        f"piso vale SÓ para cartas; câmbio USD→BRL {rate:.4f})"
    )
    lines.append("")

    if not items:
        lines.append("_Nenhuma oferta comparada._")
        return "\n".join(lines)

    lines.append("## 🟢 Aprovados (match exato)")
    lines.append("")
    if clean:
        lines.extend(_bucket(clean, bold_margin=True, with_match=False))
    else:
        lines.append("> Nenhum deal limpo nesta run.")

    if fuzzy:
        lines.append("")
        lines.append("## ⚠️ Aprovados com match fuzzy (validar manualmente)")
        lines.append("")
        lines.append(
            "> Match score < 1.00 — conferir a versão exata da carta no "
            "link TCG antes de decidir."
        )
        lines.append("")
        lines.extend(_bucket(fuzzy, bold_margin=False, with_match=True))

    if rejected:
        lines.append("")
        lines.append(
            f"## ❌ Reprovados (margem < {MIN_MARGIN_PERCENT:.0f}% "
            f"ou preço < R${MIN_PRICE_BRL:.0f})"
        )
        lines.append("")
        lines.extend(_bucket(rejected, bold_margin=False, with_match=True))

    return "\n".join(lines)
