"""Testes do cliente pokemontcg.io com urlopen mockado."""
import io
import json
from unittest.mock import patch

from src.collectors.pokemontcg import (
    PokemonTCGResult,
    _pick_best,
    fetch_price,
)


def _fake_response(payload):
    body = json.dumps(payload).encode("utf-8")
    fake = io.BytesIO(body)
    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda *a: False
    return fake


def _payload_with_cards(*cards):
    return {"data": list(cards), "totalCount": len(cards)}


def _card(name, set_name, number, prices, url=""):
    return {
        "name": name,
        "set": {"name": set_name},
        "number": number,
        "tcgplayer": {"url": url, "prices": prices},
    }


class TestPickBest:
    def test_picks_lowest_market_across_cards(self):
        cards = [
            _card("X", "S", "1", {"holofoil": {"market": 20.0}}),
            _card("X", "S", "2", {"holofoil": {"market": 5.0}}),
            _card("X", "S", "3", {"holofoil": {"market": 12.0}}),
        ]
        card, variant, price = _pick_best(cards, None, "market")
        assert card["number"] == "2"
        assert variant == "holofoil"
        assert price == 5.0

    def test_skips_cards_without_prices(self):
        cards = [
            _card("X", "S", "1", {}),
            _card("X", "S", "2", {"holofoil": {"market": 8.0}}),
        ]
        card, variant, _ = _pick_best(cards, None, "market")
        assert card["number"] == "2"

    def test_returns_none_when_no_card_has_prices(self):
        cards = [_card("X", "S", "1", {}), _card("X", "S", "2", {})]
        card, _, _ = _pick_best(cards, None, "market")
        assert card is None

    def test_respects_explicit_variant(self):
        cards = [
            _card("X", "S", "1", {"holofoil": {"market": 5.0}}),
            _card("X", "S", "2", {"normal": {"market": 10.0}}),
        ]
        # Restringindo a "normal" deve ignorar o "1" (que so tem holofoil).
        card, variant, _ = _pick_best(cards, "normal", "market")
        assert card["number"] == "2"
        assert variant == "normal"

    def test_falls_back_through_variant_priority(self):
        cards = [
            _card("X", "S", "1", {"normal": {"market": 10.0}}),
        ]
        # Sem holofoil, deve usar normal (proximo na prioridade).
        card, variant, _ = _pick_best(cards, None, "market")
        assert card["number"] == "1"
        assert variant == "normal"


class TestFetchPrice:
    def test_returns_result_on_success(self):
        payload = _payload_with_cards(
            _card(
                "Charizard ex",
                "Obsidian Flames",
                "125",
                {"holofoil": {"market": 6.12}},
                url="https://tcg/cha",
            )
        )
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("Charizard ex", "Obsidian Flames", delay_after=0)
        assert isinstance(r, PokemonTCGResult)
        assert r.price_usd == 6.12
        assert r.variant == "holofoil"
        assert r.url == "https://tcg/cha"

    def test_returns_none_when_api_returns_no_cards(self):
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(_payload_with_cards()),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("Nope", "Nope", delay_after=0)
        assert r is None

    def test_returns_none_on_network_error(self):
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            side_effect=TimeoutError("simulado"),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "Y", delay_after=0)
        assert r is None

    def test_card_number_is_included_in_query(self):
        payload = _payload_with_cards(
            _card("X", "S", "42", {"holofoil": {"market": 1.0}})
        )
        captured = {}

        class _FakeReq:
            def __init__(self, url, headers=None):
                captured["url"] = url
                captured["headers"] = headers

        with patch(
            "src.collectors.pokemontcg.urllib.request.Request", _FakeReq
        ), patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            fetch_price("X", "S", card_number="42", delay_after=0)

        assert "number" in captured["url"]
        assert "42" in captured["url"]
