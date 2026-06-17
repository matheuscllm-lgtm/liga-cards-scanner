"""Gerador da tabela markdown de ENTREGA (a saida canonica do scanner).

O resultado de um scan da Liga e entregue ao operador como UMA tabela
markdown no chat (terminal ou app) — NUNCA como arquivo .xlsx/.csv por
padrao (regra cross-scanner do operador, 2026-06-06). Esta tabela e a
fonte unica de verdade da entrega: ela NUNCA deve ser montada a mao.

Colunas canonicas (alinhadas com os outros scanners de singles):

- **Carta**: nome + numero do card (ex. ``Umbreon ex #161``). O numero
  vem do `Comparison.card_number` (preenchido pelo matcher); sem numero,
  so o nome.
- **Set**, **Liga R$**, **Ref TCG R$/US$**, **Margem %**, **Status**.
- **Links**: ``[oferta](url) · [referencia de preco](url)`` — clicaveis,
  verificaveis. SEMPRE os dois lados (oferta na Liga + referencia TCG).
- **Nota**: deals com match fuzzy (match_score < 1.0) ou preco-ancora
  fraco saem marcados com "validar manualmente" — o operador confere a
  versao exata da carta antes de decidir.

Mostra TODOS os deals comparados (aprovados E rejeitados), ordenados por
margem — nao e amostra curada. O operador filtra por conta propria.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita import circular em runtime
    from src.matching.card_matcher import Comparison

# Abaixo disto, o match e fuzzy o suficiente p/ pedir conferencia manual.
SUSPECT_MATCH_SCORE = 1.0


def _carta(c: "Comparison") -> str:
    """Nome + numero do card, ex. 'Umbreon ex #161'."""
    num = (c.card_number or "").strip()
    return f"{c.card_name} #{num}" if num else c.card_name


def _links(c: "Comparison") -> str:
    """Celula de links clicaveis: oferta na Liga + referencia de preco TCG."""
    parts = []
    if c.liga_url:
        parts.append(f"[oferta]({c.liga_url})")
    if c.tcg_url:
        parts.append(f"[referência de preço]({c.tcg_url})")
    return " · ".join(parts) if parts else "—"


def _nota(c: "Comparison") -> str:
    """Flag por linha. Match fuzzy => conferir a versao exata da carta."""
    if c.match_score < SUSPECT_MATCH_SCORE:
        return f"validar manualmente (match {c.match_score:.2f})"
    return ""


def _escape(text: str) -> str:
    """Neutraliza o pipe pra nao quebrar a coluna do markdown."""
    return text.replace("|", "\\|")


def build_markdown(items: list["Comparison"], rate: float) -> str:
    """Monta a tabela markdown de entrega (string pronta pra imprimir)."""
    from src.pricing.margin import MIN_MARGIN_PERCENT, MIN_PRICE_BRL

    approved = [c for c in items if c.status == "approved"]
    lines: list[str] = []
    lines.append(
        f"**Liga Pokémon — {len(items)} ofertas comparadas, "
        f"{len(approved)} aprovadas** "
        f"(margem bruta ≥ {MIN_MARGIN_PERCENT:.0f}% e preço ≥ "
        f"R${MIN_PRICE_BRL:.0f}; câmbio USD→BRL {rate:.4f})"
    )
    lines.append("")

    if not items:
        lines.append("_Nenhuma oferta comparada._")
        return "\n".join(lines)

    header = (
        "| Carta | Set | Liga R$ | Ref TCG R$ | Ref TCG US$ | "
        "Margem % | Status | Links | Nota |"
    )
    sep = "|---|---|---:|---:|---:|---:|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for c in items:
        lines.append(
            "| " + " | ".join([
                _escape(_carta(c)),
                _escape(c.set_name),
                f"{c.price_liga_brl:.2f}",
                f"{c.price_tcg_brl:.2f}",
                f"{c.price_tcg_usd:.2f}",
                f"{c.margin_percent:.2f}",
                c.status,
                _links(c),
                _escape(_nota(c)),
            ]) + " |"
        )
    return "\n".join(lines)
