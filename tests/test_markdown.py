"""Testes do gerador da tabela markdown de ENTREGA (saida canonica).

Garante o contrato de entrega do operador — formato padrao da frota
(espelho do myp_summary.py, 2026-07-02): 3 buckets (aprovados exatos /
fuzzy "validar manualmente" / reprovados), colunas do bucket limpo do MYP,
links `[oferta](url) · [TCG](url)`, Carta = nome + numero (sem `#`),
moedas/percentual formatados, e TODOS os deals.
"""
from __future__ import annotations

from src.matching.card_matcher import Comparison
from src.reporting.markdown import (
    build_markdown,
    carta_label,
    fmt_brl,
    fmt_pct,
    fmt_usd,
)


def _comp(**kw) -> Comparison:
    base = dict(
        card_name="Umbreon ex",
        set_name="Prismatic Evolutions",
        price_liga_brl=800.0,
        price_tcg_usd=300.0,
        price_tcg_brl=1560.0,
        margin_percent=95.0,
        exchange_rate=5.20,
        liga_url="https://liga/u",
        tcg_url="https://tcg/u",
        status="approved",
        match_score=1.0,
        card_number="161",
    )
    base.update(kw)
    return Comparison(**base)


class TestFormatHelpers:
    def test_fmt_brl_thousands_and_decimals(self):
        assert fmt_brl(1234.56) == "R$1.234,56"
        assert fmt_brl(800.0) == "R$800,00"

    def test_fmt_brl_none_is_dash(self):
        assert fmt_brl(None) == "—"

    def test_fmt_usd_thousands_and_decimals(self):
        assert fmt_usd(1234.56) == "US$1,234.56"
        assert fmt_usd(300.0) == "US$300.00"

    def test_fmt_usd_none_is_dash(self):
        assert fmt_usd(None) == "—"

    def test_fmt_pct_is_already_percent_no_x100(self):
        # margin_percent da Liga JA e percentual (95.0) — nunca multiplicar
        # por 100 como o fmt_pct do MYP (la a margem e fracao).
        assert fmt_pct(95.0) == "95.0%"
        assert fmt_pct(30.0) == "30.0%"

    def test_fmt_pct_none_is_dash(self):
        assert fmt_pct(None) == "—"

    def test_carta_label_name_plus_number_no_hash(self):
        assert carta_label("Umbreon ex", "161") == "Umbreon ex 161"

    def test_carta_label_without_number(self):
        assert carta_label("Umbreon ex", "") == "Umbreon ex"

    def test_carta_label_does_not_duplicate_number(self):
        assert carta_label("Umbreon ex 161", "161") == "Umbreon ex 161"


class TestBuildMarkdown:
    def test_header_columns_are_myp_format(self):
        md = build_markdown([_comp()], 5.20)
        assert (
            "| # | Margem % | Liga R$ | TCG US$ | Dif | Carta | Set | "
            "Raridade | Cond | Qtd | Links |"
        ) in md

    def test_carta_has_name_and_number_without_hash(self):
        md = build_markdown([_comp(card_number="161")], 5.20)
        assert "Umbreon ex 161" in md
        assert "#161" not in md

    def test_carta_falls_back_to_name_without_number(self):
        md = build_markdown([_comp(card_number="")], 5.20)
        assert "Umbreon ex" in md
        assert "Umbreon ex 161" not in md

    def test_links_are_clickable_with_tcg_label(self):
        md = build_markdown([_comp()], 5.20)
        assert "[oferta](https://liga/u)" in md
        assert "[TCG](https://tcg/u)" in md
        assert "referência de preço" not in md

    def test_prices_and_margin_are_formatted(self):
        md = build_markdown([_comp()], 5.20)
        assert "R$800,00" in md          # Liga R$
        assert "US$300.00" in md         # TCG US$
        assert "95.0%" in md             # Margem %

    def test_dif_is_tcg_brl_minus_liga_brl(self):
        md = build_markdown([_comp()], 5.20)
        assert "R$760,00" in md          # 1560 - 800

    def test_exact_approved_goes_to_green_bucket_with_bold_margin(self):
        md = build_markdown([_comp()], 5.20)
        assert "## 🟢 Aprovados (match exato)" in md
        assert "**95.0%**" in md

    def test_fuzzy_approved_goes_to_validar_bucket_with_score(self):
        md = build_markdown([_comp(match_score=0.91)], 5.20)
        assert "validar manualmente" in md
        assert "0.91" in md
        assert "**95.0%**" not in md     # negrito so no bucket limpo

    def test_exact_match_has_no_review_flag(self):
        md = build_markdown([_comp(match_score=1.0)], 5.20)
        assert "validar manualmente" not in md

    def test_match_bucket_header_has_match_column(self):
        md = build_markdown(
            [_comp(status="rejected", margin_percent=5.0)], 5.20
        )
        assert "| Qtd | Links | Match |" in md

    def test_rejected_goes_to_rejected_bucket(self):
        md = build_markdown(
            [_comp(card_name="B", status="rejected", margin_percent=5.0)],
            5.20,
        )
        assert "## ❌ Reprovados" in md
        assert "| B " in md

    def test_shows_all_deals_across_buckets(self):
        items = [
            _comp(card_name="A", status="approved"),
            _comp(card_name="B", status="approved", match_score=0.91),
            _comp(card_name="C", status="rejected", margin_percent=5.0),
        ]
        md = build_markdown(items, 5.20)
        assert "| A " in md
        assert "| B " in md
        assert "| C " in md

    def test_cond_is_nm_and_missing_fields_are_dash(self):
        md = build_markdown([_comp()], 5.20)
        assert "| NM |" in md            # Cond (invariante NM-only)
        assert "| — | NM | — |" in md    # Raridade / Cond / Qtd

    def test_empty_clean_bucket_prints_placeholder(self):
        md = build_markdown(
            [_comp(status="rejected", margin_percent=5.0)], 5.20
        )
        assert "Nenhum deal limpo" in md

    def test_header_reports_counts_and_params(self):
        items = [_comp(status="approved"), _comp(status="rejected")]
        md = build_markdown(items, 5.20)
        assert "2 ofertas comparadas" in md
        assert "1 aprovadas" in md
        assert "≥ 30%" in md
        assert "R$50" in md
        assert "5.2000" in md

    def test_header_says_floor_is_cards_only(self):
        md = build_markdown([_comp()], 5.20)
        assert "piso vale SÓ para cartas" in md

    def test_empty_is_handled(self):
        md = build_markdown([], 5.20)
        assert "Nenhuma oferta" in md

    def test_pipe_in_name_is_escaped(self):
        md = build_markdown([_comp(card_name="A|B")], 5.20)
        assert "A\\|B" in md
