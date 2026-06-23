"""Testes do cliente pokemontcg.io com urlopen mockado."""
import io
import json
from unittest.mock import patch

from src.collectors.pokemontcg import (
    PokemonTCGResult,
    _build_headers,
    _clean_secret,
    _pick_best,
    fetch_price,
)

# Escapes (nunca literais invisiveis no fonte): U+FEFF = BOM, U+200B = ZWSP.
_BOM = "\ufeff"
_ZWSP = "\u200b"


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

    def test_picks_lowest_variant_within_single_card(self):
        # Regressao: card unico com holofoil:$50 + normal:$3 deve retornar o de
        # $3 (menor). O bug antigo travava na prioridade holofoil-first (break
        # na 1a variante presente) e inflava a referencia -> deal falso.
        cards = [
            _card("X", "S", "1", {
                "holofoil": {"market": 50.0},
                "normal": {"market": 3.0},
            }),
        ]
        card, variant, price = _pick_best(cards, None, "market")
        assert card["number"] == "1"
        assert variant == "normal"
        assert price == 3.0

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
            r = fetch_price("Charizard ex", "Obsidian Flames", delay_after=0, cache_dir=None)
        assert isinstance(r, PokemonTCGResult)
        assert r.price_usd == 6.12
        assert r.variant == "holofoil"
        assert r.url == "https://tcg/cha"

    def test_returns_none_when_api_returns_no_cards(self):
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(_payload_with_cards()),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("Nope", "Nope", delay_after=0, cache_dir=None)
        assert r is None

    def test_returns_none_on_network_error(self):
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            side_effect=TimeoutError("simulado"),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "Y", delay_after=0, cache_dir=None)
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
            fetch_price("X", "S", card_number="42", delay_after=0, cache_dir=None)

        assert "number" in captured["url"]
        assert "42" in captured["url"]


class TestCache:
    def test_cache_hit_skips_http(self, tmp_path):
        from src.collectors.pokemontcg import _resolve_cache_path, _save_cache

        # Pre-popula o cache para a query exata.
        query = 'name:"Cached" set.name:"S"'
        path = _resolve_cache_path(tmp_path, query)
        _save_cache(
            path,
            _payload_with_cards(_card("Cached", "S", "1", {"holofoil": {"market": 7.0}})),
        )

        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            side_effect=AssertionError("nao deveria fazer HTTP"),
        ):
            r = fetch_price("Cached", "S", delay_after=0, cache_dir=tmp_path)
        assert r is not None
        assert r.price_usd == 7.0

    def test_cache_miss_does_http_and_writes(self, tmp_path):
        payload = _payload_with_cards(_card("X", "S", "1", {"holofoil": {"market": 3.0}}))
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(payload),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "S", delay_after=0, cache_dir=tmp_path)
        assert r.price_usd == 3.0
        # Segunda chamada deve servir do cache mesmo sem rede.
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            side_effect=AssertionError("usou rede de novo"),
        ):
            r2 = fetch_price("X", "S", delay_after=0, cache_dir=tmp_path)
        assert r2.price_usd == 3.0

    def test_expired_cache_is_ignored(self, tmp_path):
        import os
        import time as _time
        from src.collectors.pokemontcg import _resolve_cache_path, _save_cache

        query = 'name:"Old" set.name:"S"'
        path = _resolve_cache_path(tmp_path, query)
        _save_cache(path, _payload_with_cards(_card("Old", "S", "1", {"holofoil": {"market": 1.0}})))
        old = _time.time() - 999999
        os.utime(path, (old, old))

        payload_new = _payload_with_cards(_card("Old", "S", "1", {"holofoil": {"market": 99.0}}))
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            return_value=_fake_response(payload_new),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("Old", "S", delay_after=0, cache_dir=tmp_path, cache_ttl=60)
        assert r.price_usd == 99.0


class TestRetry:
    def test_retries_on_timeout_then_succeeds(self, tmp_path):
        payload = _payload_with_cards(_card("X", "S", "1", {"holofoil": {"market": 2.0}}))
        attempts = []

        def fake_urlopen(req, timeout=None):
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError("simulado")
            return _fake_response(payload)

        with patch("src.collectors.pokemontcg.urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "S", delay_after=0, cache_dir=None, retry_attempts=3)
        assert r is not None
        assert len(attempts) == 3

    def test_gives_up_after_max_attempts(self, tmp_path):
        with patch(
            "src.collectors.pokemontcg.urllib.request.urlopen",
            side_effect=TimeoutError("simulado"),
        ), patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "S", delay_after=0, cache_dir=None, retry_attempts=2)
        assert r is None

    def test_no_retry_on_404(self, tmp_path):
        import urllib.error as _err

        attempts = []

        def fake_urlopen(req, timeout=None):
            attempts.append(1)
            raise _err.HTTPError("url", 404, "Not Found", {}, None)

        with patch("src.collectors.pokemontcg.urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("src.collectors.pokemontcg.time.sleep"):
            r = fetch_price("X", "S", delay_after=0, cache_dir=None, retry_attempts=3)
        assert r is None
        assert len(attempts) == 1  # nao retentou


class TestCleanSecret:
    """_clean_secret: sanitiza BOM/zero-width/whitespace; vazio -> None."""

    def test_strips_bom_and_zero_width_and_whitespace(self):
        assert _clean_secret(_BOM + "abc123") == "abc123"
        assert _clean_secret(_ZWSP + "abc123") == "abc123"
        assert _clean_secret(_BOM + "  abc123  \n") == "abc123"
        assert _clean_secret("  abc123\n") == "abc123"

    def test_none_and_empty_after_clean_return_none(self):
        assert _clean_secret(None) is None
        assert _clean_secret("") is None
        assert _clean_secret("   ") is None
        # So-BOM / so-zero-width nao viram header invalido.
        assert _clean_secret(_BOM) is None
        assert _clean_secret(_ZWSP + _BOM) is None

    def test_preserves_clean_value(self):
        assert _clean_secret("deadbeef-1234") == "deadbeef-1234"


class TestApiKeyHeader:
    """X-Api-Key so e anexado quando POKEMONTCG_API_KEY esta presente/limpa.

    Sem rede: testa a construcao do header diretamente via _build_headers.
    Comportamento anonimo (sem chave) tem de continuar valido — CI roda sem
    a chave e nao pode quebrar.
    """

    def test_no_api_key_header_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("POKEMONTCG_API_KEY", raising=False)
        headers = _build_headers("ua/1.0")
        assert "X-Api-Key" not in headers
        assert headers["User-Agent"] == "ua/1.0"
        assert headers["Accept"] == "application/json"

    def test_no_api_key_header_when_env_empty_or_invisible(self, monkeypatch):
        for blank in ("", "   ", _BOM, _ZWSP, _ZWSP + _BOM + "  "):
            monkeypatch.setenv("POKEMONTCG_API_KEY", blank)
            headers = _build_headers("ua/1.0")
            assert "X-Api-Key" not in headers, f"blank={blank!r} nao deveria virar header"

    def test_api_key_header_present_and_clean(self, monkeypatch):
        monkeypatch.setenv("POKEMONTCG_API_KEY", "my-secret-key-1234")
        headers = _build_headers("ua/1.0")
        assert headers["X-Api-Key"] == "my-secret-key-1234"

    def test_bom_prefixed_key_is_cleaned_and_latin1_encodable(self, monkeypatch):
        # Chave salva como UTF-8-with-BOM / copy-paste do site: BOM + zero-width.
        monkeypatch.setenv("POKEMONTCG_API_KEY", _BOM + " my-secret-key-1234 " + _ZWSP)
        headers = _build_headers("ua/1.0")
        value = headers["X-Api-Key"]
        assert value == "my-secret-key-1234"
        # Headers HTTP sao codificados em latin-1 pelo urllib: o BOM cru
        # (U+FEFF) lancaria UnicodeEncodeError. Limpo, codifica sem erro.
        assert value.encode("latin-1") == b"my-secret-key-1234"

    def test_built_request_carries_clean_header(self, monkeypatch):
        # Constroi o Request de verdade (sem rede) e confere o header montado.
        import urllib.request

        monkeypatch.setenv("POKEMONTCG_API_KEY", _BOM + "abc-key-789")
        req = urllib.request.Request(
            "https://api.pokemontcg.io/v2/cards", headers=_build_headers("ua/1.0")
        )
        # urllib normaliza chaves de header para Capitalized.
        assert req.get_header("X-api-key") == "abc-key-789"
        req.get_header("X-api-key").encode("latin-1")  # nao levanta
