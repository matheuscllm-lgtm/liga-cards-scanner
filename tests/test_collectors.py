"""Testes dos coletores TCGplayer e Liga em modo mock e CSV."""
import pytest

from src.collectors.liga_pokemon import (
    DEFAULT_CSV_PATH as LIGA_DEFAULT_CSV_PATH,
    LigaOffer,
    fetch_offers,
)
from src.collectors.tcgplayer import (
    DEFAULT_CSV_PATH,
    TCGReference,
    fetch_reference_prices,
)


class TestMockMode:
    def test_returns_list_of_references(self):
        refs = fetch_reference_prices()
        assert isinstance(refs, list)
        assert all(isinstance(r, TCGReference) for r in refs)
        assert len(refs) >= 1


class TestCsvMode:
    def _write_csv(self, tmp_path, body, header="card_name,set_name,market_price_usd,url\n"):
        path = tmp_path / "tcg.csv"
        path.write_text(header + body, encoding="utf-8")
        return path

    def test_loads_well_formed_csv(self, tmp_path):
        path = self._write_csv(
            tmp_path,
            "Charizard ex,Obsidian Flames,55.00,https://tcg/cha\n"
            "Pikachu V,Vivid Voltage,14.00,\n",
        )
        refs = fetch_reference_prices(source="csv", csv_path=path)
        assert len(refs) == 2
        assert refs[0].card_name == "Charizard ex"
        assert refs[0].price_usd == 55.00
        assert refs[0].url == "https://tcg/cha"
        assert refs[1].url == ""

    def test_url_column_is_optional(self, tmp_path):
        path = self._write_csv(
            tmp_path,
            "Iono,Paldea Evolved,12.00\n",
            header="card_name,set_name,market_price_usd\n",
        )
        refs = fetch_reference_prices(source="csv", csv_path=path)
        assert len(refs) == 1
        assert refs[0].url == ""

    def test_ignores_comment_lines(self, tmp_path):
        path = tmp_path / "tcg.csv"
        path.write_text(
            "# comentario antes do header\n"
            "card_name,set_name,market_price_usd\n"
            "# mais um comentario\n"
            "Mew,Fusion Strike,32.00\n",
            encoding="utf-8",
        )
        refs = fetch_reference_prices(source="csv", csv_path=path)
        assert len(refs) == 1

    def test_skips_invalid_price(self, tmp_path, caplog):
        path = self._write_csv(
            tmp_path,
            "Ok,Set X,10.00,\n"
            "Quebrado,Set X,not_a_number,\n"
            "Outro,Set X,5.00,\n",
        )
        refs = fetch_reference_prices(source="csv", csv_path=path)
        assert [r.card_name for r in refs] == ["Ok", "Outro"]

    def test_raises_on_missing_required_columns(self, tmp_path):
        path = tmp_path / "tcg.csv"
        path.write_text("card_name,set_name\nA,B\n", encoding="utf-8")
        with pytest.raises(ValueError, match="market_price_usd"):
            fetch_reference_prices(source="csv", csv_path=path)

    def test_raises_when_file_missing(self, tmp_path):
        missing = tmp_path / "nao_existe.csv"
        with pytest.raises(FileNotFoundError):
            fetch_reference_prices(source="csv", csv_path=missing)

    def test_env_var_overrides_default_path(self, tmp_path, monkeypatch):
        path = self._write_csv(tmp_path, "Card,Set,10.00,\n")
        monkeypatch.setenv("LIGA_TCG_SOURCE", "csv")
        monkeypatch.setenv("LIGA_TCG_CSV", str(path))
        refs = fetch_reference_prices(source="csv")
        assert len(refs) == 1
        assert refs[0].card_name == "Card"

    def test_default_csv_path_lives_in_data_dir(self):
        assert DEFAULT_CSV_PATH.name == "tcgplayer_prices.csv"
        assert DEFAULT_CSV_PATH.parent.name == "data"


class TestUnknownSource:
    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="Source desconhecido"):
            fetch_reference_prices(source="ftp")

    def test_api_mode_is_stub(self):
        with pytest.raises(NotImplementedError):
            fetch_reference_prices(source="api")


class TestPokemontcgMode:
    def test_requires_queries(self):
        with pytest.raises(ValueError, match="queries"):
            fetch_reference_prices(source="pokemontcg")

    def test_calls_fetch_price_per_query(self, monkeypatch):
        from src.collectors import pokemontcg as pkm

        calls = []

        def fake_fetch_price(name, set_, **kwargs):
            calls.append((name, set_))
            return pkm.PokemonTCGResult(
                card_name=name,
                set_name=set_,
                card_number="1",
                price_usd=10.0,
                url=f"https://tcg/{name}",
                variant="holofoil",
            )

        monkeypatch.setattr(
            "src.collectors.pokemontcg.fetch_price", fake_fetch_price
        )
        refs = fetch_reference_prices(
            source="pokemontcg",
            queries=[("Charizard ex", "Obsidian Flames"), ("Pikachu V", "Vivid Voltage")],
        )
        assert len(refs) == 2
        assert calls == [
            ("Charizard ex", "Obsidian Flames"),
            ("Pikachu V", "Vivid Voltage"),
        ]
        assert refs[0].price_usd == 10.0
        assert refs[0].url == "https://tcg/Charizard ex"

    def test_skips_when_api_returns_none(self, monkeypatch):
        def fake_fetch_price(name, set_, **kwargs):
            return None if name == "Missing" else type(
                "R", (), dict(
                    card_name=name, set_name=set_, card_number="1",
                    price_usd=5.0, url="", variant="normal",
                ),
            )()

        monkeypatch.setattr(
            "src.collectors.pokemontcg.fetch_price", fake_fetch_price
        )
        refs = fetch_reference_prices(
            source="pokemontcg",
            queries=[("Found", "S"), ("Missing", "S"), ("Found2", "S")],
        )
        assert [r.card_name for r in refs] == ["Found", "Found2"]


class TestLigaMockMode:
    def test_returns_list_of_offers(self):
        offers = fetch_offers()
        assert isinstance(offers, list)
        assert all(isinstance(o, LigaOffer) for o in offers)
        assert len(offers) >= 1


class TestLigaCsvMode:
    HEADER = "card_name,set_name,price_brl,url,condition,seller\n"

    def _write_csv(self, tmp_path, body, header=HEADER):
        path = tmp_path / "liga.csv"
        path.write_text(header + body, encoding="utf-8")
        return path

    def test_loads_well_formed_csv(self, tmp_path):
        path = self._write_csv(
            tmp_path,
            "Charizard ex,Obsidian Flames,180.00,https://liga/c,NM,LojaA\n"
            "Pikachu V,Vivid Voltage,65.00,https://liga/p,,\n",
        )
        offers = fetch_offers(source="csv", csv_path=path)
        assert len(offers) == 2
        assert offers[0].card_name == "Charizard ex"
        assert offers[0].price_brl == 180.00
        assert offers[0].seller == "LojaA"
        assert offers[1].condition == "NM"  # default quando vazio

    def test_optional_columns_default_nicely(self, tmp_path):
        path = tmp_path / "liga.csv"
        path.write_text(
            "card_name,set_name,price_brl,url\n"
            "Iono,Paldea Evolved,45.00,https://liga/i\n",
            encoding="utf-8",
        )
        offers = fetch_offers(source="csv", csv_path=path)
        assert len(offers) == 1
        assert offers[0].condition == "NM"
        assert offers[0].seller == ""

    def test_ignores_comment_lines(self, tmp_path):
        path = tmp_path / "liga.csv"
        path.write_text(
            "# header comment\n"
            "card_name,set_name,price_brl,url\n"
            "# midline\n"
            "Mew VMAX,Fusion Strike,120.00,https://liga/m\n",
            encoding="utf-8",
        )
        offers = fetch_offers(source="csv", csv_path=path)
        assert len(offers) == 1

    def test_skips_invalid_price(self, tmp_path):
        path = self._write_csv(
            tmp_path,
            "Ok,Set X,100.00,https://liga/o,,\n"
            "Quebrado,Set X,not_a_number,https://liga/q,,\n"
            "Outro,Set X,50.00,https://liga/x,,\n",
        )
        offers = fetch_offers(source="csv", csv_path=path)
        assert [o.card_name for o in offers] == ["Ok", "Outro"]

    def test_raises_on_missing_required_columns(self, tmp_path):
        path = tmp_path / "liga.csv"
        path.write_text("card_name,set_name\nA,B\n", encoding="utf-8")
        with pytest.raises(ValueError, match="price_brl"):
            fetch_offers(source="csv", csv_path=path)

    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fetch_offers(source="csv", csv_path=tmp_path / "nao_existe.csv")

    def test_env_var_overrides_default_path(self, tmp_path, monkeypatch):
        path = self._write_csv(tmp_path, "Card,Set,100.00,https://liga/c,,\n")
        monkeypatch.setenv("LIGA_OFFERS_CSV", str(path))
        offers = fetch_offers(source="csv")
        assert len(offers) == 1
        assert offers[0].card_name == "Card"

    def test_default_csv_path_lives_in_data_dir(self):
        assert LIGA_DEFAULT_CSV_PATH.name == "liga_offers.csv"
        assert LIGA_DEFAULT_CSV_PATH.parent.name == "data"


class TestLigaUnknownSource:
    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="Source desconhecido"):
            fetch_offers(source="ftp")

    def test_http_mode_is_stub(self):
        with pytest.raises(NotImplementedError):
            fetch_offers(source="http")
