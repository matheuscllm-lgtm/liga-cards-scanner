"""Smoke tests: garantem que o pipeline mockado roda ponta a ponta.

Testes unitários específicos (margin, currency, matching, filters) virão
em PRs subsequentes.
"""
from src.collectors.liga_pokemon import fetch_offers
from src.collectors.tcgplayer import fetch_reference_prices
from src.matching.card_matcher import match_cards


def test_pipeline_runs_with_mock_data():
    offers = fetch_offers()
    refs = fetch_reference_prices()
    comparisons = match_cards(offers, refs, exchange_rate=5.20)

    assert comparisons, "matcher deveria produzir ao menos uma comparação"

    margins = [c.margin_percent for c in comparisons]
    assert margins == sorted(margins, reverse=True), (
        "comparações devem vir ordenadas por margem decrescente"
    )

    assert any(c.status == "approved" for c in comparisons)
    assert any(c.status == "rejected" for c in comparisons)
