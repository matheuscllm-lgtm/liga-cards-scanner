"""Testes para src/matching/normalization.py e card_matcher.py."""
import pytest

from src.collectors.liga_pokemon import LigaOffer
from src.collectors.tcgplayer import TCGReference
from src.matching.card_matcher import (
    FUZZY_MATCH_THRESHOLD,
    match_cards,
)
from src.matching.normalization import (
    SET_ALIASES,
    normalize_card_name,
    normalize_set_name,
    normalize_text,
)


class TestNormalizeText:
    def test_strips_accents(self):
        assert normalize_text("Pokémon") == "pokemon"

    def test_lowercases(self):
        assert normalize_text("Charizard EX") == "charizard ex"

    def test_collapses_whitespace(self):
        assert normalize_text("  Mew   VMAX  ") == "mew vmax"

    def test_handles_empty(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestNormalizeCardName:
    def test_vmax_variants_collapse(self):
        assert normalize_card_name("Mew V-MAX") == "mew vmax"
        assert normalize_card_name("Mew V MAX") == "mew vmax"
        assert normalize_card_name("Mew VMAX") == "mew vmax"

    def test_vstar_variants_collapse(self):
        assert normalize_card_name("Giratina V-STAR") == "giratina vstar"
        assert normalize_card_name("Giratina V STAR") == "giratina vstar"
        assert normalize_card_name("Giratina VSTAR") == "giratina vstar"

    def test_vunion_variants_collapse(self):
        assert normalize_card_name("Mewtwo V-UNION") == "mewtwo vunion"
        assert normalize_card_name("Mewtwo V UNION") == "mewtwo vunion"


class TestNormalizeSetName:
    def test_resolves_known_aliases(self):
        assert normalize_set_name("OBF") == "obsidian flames"
        assert normalize_set_name("LOR") == "lost origin"
        assert normalize_set_name("S&V") == "scarlet & violet"
        assert normalize_set_name("SV") == "scarlet & violet"

    def test_passes_through_unknown(self):
        # Sem alias: apenas normaliza (lowercase, sem acentos).
        assert normalize_set_name("Some Unknown Set") == "some unknown set"

    def test_aliases_dict_has_all_lowercase_values(self):
        for alias, canonical in SET_ALIASES.items():
            assert alias == alias.lower()
            assert canonical == canonical.lower()


class TestMatchCards:
    def _offer(self, name, set_, price=100.0):
        return LigaOffer(
            card_name=name,
            set_name=set_,
            price_brl=price,
            url=f"https://liga/{name}",
        )

    def _ref(self, name, set_, usd=10.0):
        return TCGReference(
            card_name=name,
            set_name=set_,
            price_usd=usd,
            url=f"https://tcg/{name}",
        )

    def test_exact_match_score_is_one(self):
        offers = [self._offer("Charizard ex", "Obsidian Flames")]
        refs = [self._ref("Charizard ex", "Obsidian Flames")]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].match_score == 1.0

    def test_alias_set_matches_canonical(self):
        # "OBF" no liga deve casar com "Obsidian Flames" no TCG via alias.
        offers = [self._offer("Charizard ex", "OBF")]
        refs = [self._ref("Charizard ex", "Obsidian Flames")]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].match_score == 1.0

    def test_vmax_variant_matches_vmax(self):
        # "V-MAX" liga deve casar com "VMAX" TCG via normalização.
        offers = [self._offer("Mew V-MAX", "Fusion Strike")]
        refs = [self._ref("Mew VMAX", "Fusion Strike")]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert len(result) == 1
        assert result[0].match_score == 1.0

    def test_unmatched_card_is_skipped(self):
        offers = [self._offer("Pikachu V", "Vivid Voltage")]
        refs = [self._ref("Charizard ex", "Obsidian Flames")]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert result == []

    def test_non_positive_offer_price_is_skipped(self):
        # Preco Liga <= 0 nao gera margem valida; deve ser pulado em vez de
        # propagar ValueError de calculate_margin e abortar o scan inteiro.
        offers = [
            self._offer("Charizard ex", "Obsidian Flames", price=0.0),
            self._offer("Pikachu V", "Vivid Voltage", price=-10.0),
            self._offer("Mew VMAX", "Fusion Strike", price=80.0),
        ]
        refs = [
            self._ref("Charizard ex", "Obsidian Flames"),
            self._ref("Pikachu V", "Vivid Voltage"),
            self._ref("Mew VMAX", "Fusion Strike"),
        ]
        result = match_cards(offers, refs, exchange_rate=5.0)
        assert [r.card_name for r in result] == ["Mew VMAX"]

    def test_low_threshold_admits_loose_match(self):
        # Set escrito errado mas nome bate. Com threshold baixo, aceita.
        offers = [self._offer("Charizard ex", "Obsdian Flms")]
        refs = [self._ref("Charizard ex", "Obsidian Flames")]
        result = match_cards(
            offers, refs, exchange_rate=5.0, fuzzy_threshold=0.7
        )
        assert len(result) == 1
        assert result[0].match_score < 1.0
        assert result[0].match_score >= 0.7

    def test_high_threshold_rejects_loose_match(self):
        # Mesmo input do teste anterior, mas threshold alto rejeita.
        offers = [self._offer("Pikachu V", "Some Random Set")]
        refs = [self._ref("Charizard ex", "Obsidian Flames")]
        result = match_cards(
            offers, refs, exchange_rate=5.0, fuzzy_threshold=0.95
        )
        assert result == []

    def test_default_threshold_is_documented(self):
        assert FUZZY_MATCH_THRESHOLD == 0.85

    def test_results_sorted_by_margin_desc(self):
        offers = [
            self._offer("A", "Set X", price=100.0),
            self._offer("B", "Set X", price=100.0),
            self._offer("C", "Set X", price=100.0),
        ]
        refs = [
            self._ref("A", "Set X", usd=10.0),   # margem -50%
            self._ref("B", "Set X", usd=30.0),   # margem +50%
            self._ref("C", "Set X", usd=20.0),   # margem 0%
        ]
        result = match_cards(offers, refs, exchange_rate=5.0)
        margins = [r.margin_percent for r in result]
        assert margins == sorted(margins, reverse=True)
