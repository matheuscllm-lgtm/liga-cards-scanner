"""Testes para src/pricing/currency.py."""
import pytest

from src.pricing.currency import (
    DEFAULT_USD_BRL_RATE,
    convert_usd_to_brl,
    get_exchange_rate,
)


class TestConvertUsdToBrl:
    def test_multiplies_by_explicit_rate(self):
        assert convert_usd_to_brl(10.0, rate=5.0) == 50.0

    def test_rounds_to_two_decimals(self):
        # 3.333... * 3 = 9.999... -> arredonda para 10.00
        assert convert_usd_to_brl(3.3333, rate=3.0) == 10.00

    def test_zero_amount(self):
        assert convert_usd_to_brl(0.0, rate=5.20) == 0.0

    def test_uses_env_rate_when_no_arg(self, monkeypatch):
        monkeypatch.setenv("LIGA_USD_BRL_RATE", "6.00")
        assert convert_usd_to_brl(10.0) == 60.00

    def test_falls_back_to_default_when_no_env(self, monkeypatch):
        monkeypatch.delenv("LIGA_USD_BRL_RATE", raising=False)
        assert convert_usd_to_brl(10.0) == pytest.approx(
            10.0 * DEFAULT_USD_BRL_RATE
        )


class TestGetExchangeRate:
    def test_returns_env_value_when_set(self, monkeypatch):
        monkeypatch.setenv("LIGA_USD_BRL_RATE", "5.55")
        assert get_exchange_rate() == 5.55

    def test_returns_default_when_env_absent(self, monkeypatch):
        monkeypatch.delenv("LIGA_USD_BRL_RATE", raising=False)
        assert get_exchange_rate() == DEFAULT_USD_BRL_RATE

    def test_default_is_documented_constant(self):
        # Quem mudar a taxa fallback deve atualizar conscientemente.
        assert DEFAULT_USD_BRL_RATE == 5.20
