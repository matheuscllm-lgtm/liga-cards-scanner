"""Testes do gerador da tabela markdown de ENTREGA (saida canonica).

Garante o contrato de entrega do operador (2026-06-06): a entrega de um
scan e UMA tabela markdown com links clicaveis (oferta + referencia de
preco), Carta = nome + numero, e TODOS os deals.
"""
from __future__ import annotations

from src.matching.card_matcher import Comparison
from src.reporting.markdown import build_markdown


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


class TestBuildMarkdown:
    def test_is_markdown_table_with_header_and_separator(self):
        md = build_markdown([_comp()], 5.20)
        assert "| Carta | Set |" in md
        assert "|---|" in md

    def test_carta_column_has_name_and_number(self):
        md = build_markdown([_comp(card_number="161")], 5.20)
        assert "Umbreon ex #161" in md

    def test_carta_column_falls_back_to_name_without_number(self):
        md = build_markdown([_comp(card_number="")], 5.20)
        assert "Umbreon ex" in md
        assert "Umbreon ex #" not in md

    def test_links_are_clickable_both_sides(self):
        md = build_markdown([_comp()], 5.20)
        assert "[oferta](https://liga/u)" in md
        assert "[referência de preço](https://tcg/u)" in md

    def test_shows_all_deals_not_just_approved(self):
        items = [
            _comp(card_name="A", status="approved"),
            _comp(card_name="B", status="rejected", margin_percent=5.0),
        ]
        md = build_markdown(items, 5.20)
        assert "| A " in md
        assert "| B " in md
        assert "rejected" in md

    def test_fuzzy_match_is_flagged_for_manual_review(self):
        md = build_markdown([_comp(match_score=0.91)], 5.20)
        assert "validar manualmente" in md

    def test_exact_match_has_no_review_flag(self):
        md = build_markdown([_comp(match_score=1.0)], 5.20)
        assert "validar manualmente" not in md

    def test_empty_is_handled(self):
        md = build_markdown([], 5.20)
        assert "Nenhuma oferta" in md

    def test_header_reports_counts(self):
        items = [_comp(status="approved"), _comp(status="rejected")]
        md = build_markdown(items, 5.20)
        assert "2 ofertas comparadas" in md
        assert "1 aprovadas" in md

    def test_pipe_in_name_is_escaped(self):
        md = build_markdown([_comp(card_name="A|B")], 5.20)
        assert "A\\|B" in md
