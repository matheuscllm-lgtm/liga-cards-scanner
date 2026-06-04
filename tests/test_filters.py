"""Testes das regras de filtro do scanner: preço >= R$50 e margem >= 25%."""
from src.collectors.liga_pokemon import LigaOffer
from src.collectors.tcgplayer import TCGReference
from src.matching.card_matcher import match_cards


def _make_pair(price_liga: float, price_usd: float, name: str = "Card"):
    return (
        LigaOffer(
            card_name=name,
            set_name="Set",
            price_brl=price_liga,
            url=f"https://liga/{name}",
        ),
        TCGReference(
            card_name=name,
            set_name="Set",
            price_usd=price_usd,
            url=f"https://tcg/{name}",
        ),
    )


class TestFilters:
    def test_approved_when_meets_both_rules(self):
        offer, ref = _make_pair(price_liga=100.0, price_usd=30.0)
        # tcg_brl = 30 * 5 = 150; margem = 50%
        result = match_cards([offer], [ref], exchange_rate=5.0)
        assert result[0].status == "approved"

    def test_rejected_when_price_below_50(self):
        offer, ref = _make_pair(price_liga=40.0, price_usd=20.0)
        # margem boa (150%) mas preço Liga abaixo de R$50
        result = match_cards([offer], [ref], exchange_rate=5.0)
        assert result[0].status == "rejected"

    def test_rejected_when_margin_below_25(self):
        offer, ref = _make_pair(price_liga=100.0, price_usd=22.0)
        # tcg_brl = 110; margem = 10%
        result = match_cards([offer], [ref], exchange_rate=5.0)
        assert result[0].status == "rejected"

    def test_rejected_when_margin_negative(self):
        offer, ref = _make_pair(price_liga=200.0, price_usd=20.0)
        # tcg_brl = 100; margem = -50%
        result = match_cards([offer], [ref], exchange_rate=5.0)
        assert result[0].status == "rejected"

    def test_approved_exactly_at_boundary(self):
        # preço Liga exatamente R$50, margem exatamente 25%
        # tcg_brl = liga * 1.25 = 62.5; usd = 62.5 / rate
        offer, ref = _make_pair(price_liga=50.0, price_usd=62.5 / 5.0)
        result = match_cards([offer], [ref], exchange_rate=5.0)
        assert result[0].status == "approved"

    def test_custom_min_price(self):
        offer, ref = _make_pair(price_liga=60.0, price_usd=20.0)
        # margem boa, preço acima do default mas abaixo do custom 100
        result = match_cards(
            [offer], [ref], exchange_rate=5.0, min_price=100.0
        )
        assert result[0].status == "rejected"

    def test_custom_min_margin(self):
        offer, ref = _make_pair(price_liga=100.0, price_usd=30.0)
        # margem 50%, mas exige >= 75%
        result = match_cards(
            [offer], [ref], exchange_rate=5.0, min_margin=75.0
        )
        assert result[0].status == "rejected"

    def test_filters_mixed_batch(self):
        offers = []
        refs = []
        for i, (lp, up, expected) in enumerate(
            [
                (100.0, 30.0, "approved"),   # margem 50%
                (40.0, 20.0, "rejected"),    # preço < R$50
                (100.0, 22.0, "rejected"),   # margem 10%
                (200.0, 20.0, "rejected"),   # margem -50%
            ]
        ):
            name = f"Card{i}"
            o, r = _make_pair(lp, up, name=name)
            offers.append(o)
            refs.append(r)

        results = match_cards(offers, refs, exchange_rate=5.0)
        approved = [r for r in results if r.status == "approved"]
        rejected = [r for r in results if r.status == "rejected"]
        assert len(approved) == 1
        assert len(rejected) == 3
