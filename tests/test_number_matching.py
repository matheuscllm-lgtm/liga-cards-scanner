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

    def test_zero_padding_da_liga_casa_com_numero_sem_padding(self):
        # Liga: "059"; pokemontcg.io: "59". Camada 1 deve casar mesmo assim.
        refs = [_ref(number="161", usd=900.0), _ref(number="59", usd=30.0)]
        result = match_cards([_offer(number="059")], refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].price_tcg_usd == pytest.approx(30.0)
        assert result[0].match_score == 1.0

    def test_match_por_nome_com_numero_divergente_nao_e_exato(self):
        # FP real (scan 2026-08-11): oferta Blastoise ex 184 casou por nome
        # com a ref do #200 (SIR, US$137.85) e saiu "match exato" no bucket
        # aprovado. Com numeros divergentes o score cai pra < 1.0 (validar
        # manualmente).
        refs = [_ref(name="Blastoise ex", number="200", usd=137.85)]
        offers = [_offer(name="Blastoise ex", number="184", price=299.99)]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].match_score < 1.0

    def test_normalize_card_number_casos(self):
        from src.matching.normalization import normalize_card_number

        assert normalize_card_number("009") == "9"
        assert normalize_card_number("184") == "184"
        assert normalize_card_number("TG12") == "tg12"
        assert normalize_card_number(" 038 ") == "38"
        assert normalize_card_number("") == ""


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

    def test_zero_padding_da_liga_e_normalizado_na_query(self, tmp_path):
        # Cache pre-populado sob o hash da query NORMALIZADA ("009" -> "9").
        # Se fetch_price normalizar, acha o cache e responde offline; se nao,
        # tentaria rede (e o payload plantado provaria a query errada).
        import json

        from src.collectors.pokemontcg import _resolve_cache_path, fetch_price

        query = 'name:"Blastoise ex" set.name:"151" number:"9"'
        payload = {"data": [{
            "name": "Blastoise ex", "number": "9",
            "set": {"name": "151"},
            "tcgplayer": {"url": "https://tcg/9",
                          "prices": {"holofoil": {"market": 3.9}}},
        }]}
        path = _resolve_cache_path(tmp_path, query)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

        result = fetch_price(
            "Blastoise ex", "151", card_number="009", cache_dir=tmp_path,
        )
        assert result is not None
        assert result.card_number == "9"
        assert result.price_usd == pytest.approx(3.9)

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
