"""Testes para src/pricing/margin.py."""
import pytest

from src.pricing.margin import (
    MIN_MARGIN_PERCENT,
    MIN_PRICE_BRL,
    calculate_margin,
    is_approved,
)


class TestCalculateMargin:
    def test_zero_margin_when_prices_equal(self):
        assert calculate_margin(100.0, 100.0) == 0.0

    def test_positive_margin(self):
        # ((150 - 100) / 100) * 100 = 50
        assert calculate_margin(100.0, 150.0) == 50.0

    def test_negative_margin_when_tcg_lower(self):
        # ((80 - 100) / 100) * 100 = -20
        assert calculate_margin(100.0, 80.0) == -20.0

    def test_example_from_readme(self):
        # README: 80 -> 110 -> 37.5%
        assert calculate_margin(80.0, 110.0) == pytest.approx(37.5)

    def test_raises_on_zero_liga_price(self):
        with pytest.raises(ValueError):
            calculate_margin(0.0, 100.0)

    def test_raises_on_negative_liga_price(self):
        with pytest.raises(ValueError):
            calculate_margin(-10.0, 100.0)


class TestIsApproved:
    def test_approved_when_above_both_thresholds(self):
        assert is_approved(price_liga_brl=100.0, margin_percent=35.0) is True

    def test_rejected_when_margin_below_threshold(self):
        assert is_approved(price_liga_brl=100.0, margin_percent=20.0) is False

    def test_rejected_when_price_below_threshold(self):
        # Margem boa mas preço abaixo de R$50
        assert is_approved(price_liga_brl=45.0, margin_percent=40.0) is False

    def test_approved_exactly_at_thresholds(self):
        assert (
            is_approved(
                price_liga_brl=MIN_PRICE_BRL, margin_percent=MIN_MARGIN_PERCENT
            )
            is True
        )

    def test_rejected_just_below_price_threshold(self):
        assert is_approved(price_liga_brl=49.99, margin_percent=100.0) is False

    def test_rejected_just_below_margin_threshold(self):
        assert is_approved(price_liga_brl=1000.0, margin_percent=29.99) is False

    def test_custom_thresholds(self):
        # Critérios mais agressivos: preço >= 100, margem >= 50
        assert (
            is_approved(80.0, 60.0, min_price=100.0, min_margin=50.0) is False
        )
        assert (
            is_approved(120.0, 60.0, min_price=100.0, min_margin=50.0) is True
        )

    def test_default_thresholds_match_business_rules(self):
        assert MIN_PRICE_BRL == 50.0
        assert MIN_MARGIN_PERCENT == 30.0
