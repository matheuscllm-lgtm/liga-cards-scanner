"""Testes do match por numero de carta (camada 1 do matcher).

Cenario real que motivou a feature: na PRE (Prismatic Evolutions) existem
varias versoes do mesmo nome no mesmo set (ex.: Umbreon ex regular e
Special Illustration Rare). Sem o numero, o matcher casava todas no mesmo
preco de referencia — com o numero, cada versao casa com o preco certo.
"""
import pytest

from src.collectors.liga_pokemon import LigaOffer
from src.collectors.tcgplayer import TCGReference, fetch_reference_prices
from src.matching.card_matcher import match_cards


def _offer(name="Umbreon ex", number="", price=1000.0):
    return LigaOffer(
        card_name=name, set_name="Prismatic Evolutions", price_brl=price,
        url="https://liga/x", card_number=number,
    )


def _ref(name="Umbreon ex", number="", usd=100.0):
    return TCGReference(
        card_name=name, set_name="Prismatic Evolutions", price_usd=usd,
        url="https://tcg/x", card_number=number,
    )


class TestMatchPorNumero:
    def test_numero_distingue_versoes_do_mesmo_nome(self):
        refs = [_ref(number="161", usd=900.0), _ref(number="59", usd=30.0)]
        result = match_cards([_offer(number="161")], refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].price_tcg_usd == pytest.approx(900.0)
        assert result[0].match_score == 1.0

    def test_oferta_sem_numero_usa_camada_2(self):
        refs = [_ref(number="161", usd=900.0)]
        result = match_cards([_offer(number="")], refs, exchange_rate=5.0)
        # cai no indice (nome, set) e ainda casa
        assert len(result) == 1
        assert result[0].price_tcg_usd == pytest.approx(900.0)

    def test_refs_sem_numero_nao_quebram(self):
        refs = [_ref(number="", usd=100.0)]
        result = match_cards([_offer(number="161")], refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].price_tcg_usd == pytest.approx(100.0)


class TestQueriesComNumero:
    def test_pokemontcg_recebe_card_number(self, monkeypatch):
        calls = []

        def fake_fetch_price(card_name, set_name, card_number=None, **kw):
            calls.append((card_name, set_name, card_number))
            from src.collectors.pokemontcg import PokemonTCGResult
            return PokemonTCGResult(
                card_name=card_name, set_name=set_name,
                card_number=card_number or "", price_usd=10.0,
                url="https://tcg/x", variant="holofoil",
            )

        import src.collectors.pokemontcg as ptcg
        monkeypatch.setattr(ptcg, "fetch_price", fake_fetch_price)

        refs = fetch_reference_prices(
            source="pokemontcg",
            queries=[("Umbreon ex", "Prismatic Evolutions", "161"),
                     ("Pikachu", "151", "")],
        )
        assert calls == [
            ("Umbreon ex", "Prismatic Evolutions", "161"),
            ("Pikachu", "151", None),
        ]
        assert refs[0].card_number == "161"

    def test_fallback_sem_numero_quando_api_nao_acha(self, monkeypatch):
        calls = []

        def fake_fetch_price(card_name, set_name, card_number=None, **kw):
            calls.append(card_number)
            if card_number:  # com numero: nao acha
                return None
            from src.collectors.pokemontcg import PokemonTCGResult
            return PokemonTCGResult(
                card_name=card_name, set_name=set_name, card_number="",
                price_usd=5.0, url="", variant="normal",
            )

        import src.collectors.pokemontcg as ptcg
        monkeypatch.setattr(ptcg, "fetch_price", fake_fetch_price)

        refs = fetch_reference_prices(
            source="pokemontcg",
            queries=[("Charizard ex", "Obsidian Flames", "125")],
        )
        assert calls == ["125", None]  # tentou com numero, depois sem
        assert len(refs) == 1
        assert refs[0].price_usd == pytest.approx(5.0)

    def test_queries_de_pares_seguem_funcionando(self, monkeypatch):
        def fake_fetch_price(card_name, set_name, card_number=None, **kw):
            assert card_number is None
            from src.collectors.pokemontcg import PokemonTCGResult
            return PokemonTCGResult(
                card_name=card_name, set_name=set_name, card_number="1",
                price_usd=1.0, url="", variant="normal",
            )

        import src.collectors.pokemontcg as ptcg
        monkeypatch.setattr(ptcg, "fetch_price", fake_fetch_price)
        refs = fetch_reference_prices(
            source="pokemontcg", queries=[("Pikachu", "151")],
        )
        assert len(refs) == 1
