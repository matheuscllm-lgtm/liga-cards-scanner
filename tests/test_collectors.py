"""Testes do coletor TCGplayer em modo mock e CSV."""
import pytest

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
