"""Testes de integracao do src/main.py.

Exercita run() ponta a ponta em todos os modos suportados, garantindo
que arquivos de saida sao criados e que erros de configuracao se
manifestam de forma diagnostica (nao crash silencioso).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src import main as main_module


@pytest.fixture
def tmp_reports(monkeypatch, tmp_path):
    """Redireciona reports/ para tmp_path para nao poluir o repo."""
    monkeypatch.setattr(main_module, "REPORTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def deterministic_env(monkeypatch):
    """Taxa fixa em todos os testes para evitar dependencia de rede."""
    monkeypatch.setenv("LIGA_USD_BRL_RATE", "5.20")
    monkeypatch.delenv("LIGA_OFFERS_SOURCE", raising=False)
    monkeypatch.delenv("LIGA_TCG_SOURCE", raising=False)


class TestRunMockMode:
    def test_returns_comparisons(self, tmp_reports):
        comparisons = main_module.run()
        assert len(comparisons) >= 5
        assert all(hasattr(c, "margin_percent") for c in comparisons)

    def test_writes_json_csv_xlsx(self, tmp_reports):
        main_module.run()
        outputs = list(tmp_reports.iterdir())
        suffixes = sorted(p.suffix for p in outputs)
        assert ".json" in suffixes
        assert ".csv" in suffixes
        # xlsx pode nao existir se openpyxl ausente; nao falha aqui.

    def test_json_output_has_expected_fields(self, tmp_reports):
        main_module.run()
        jsons = list(tmp_reports.glob("*.json"))
        assert jsons, "deve gerar pelo menos um JSON"
        with jsons[0].open(encoding="utf-8") as fp:
            data = json.load(fp)
        assert isinstance(data, list) and data
        item = data[0]
        for key in ("card_name", "set_name", "price_liga_brl", "price_tcg_brl",
                    "margin_percent", "status"):
            assert key in item, f"campo {key!r} ausente no JSON"

    def test_csv_output_is_sortable_by_margin(self, tmp_reports):
        main_module.run()
        csvs = list(tmp_reports.glob("*.csv"))
        assert csvs
        with csvs[0].open(encoding="utf-8") as fp:
            rows = list(csv.DictReader(fp))
        margins = [float(r["margin_percent"]) for r in rows]
        assert margins == sorted(margins, reverse=True)

    def test_approved_count_uses_25_percent_threshold(self, tmp_reports):
        comparisons = main_module.run()
        for c in comparisons:
            if c.status == "approved":
                assert c.margin_percent >= 25.0
                assert c.price_liga_brl >= 50.0


class TestRunCsvMode:
    def test_liga_csv_drives_offers(self, monkeypatch, tmp_path, tmp_reports):
        csv_path = tmp_path / "liga.csv"
        csv_path.write_text(
            "card_name,set_name,price_brl,url\n"
            "Mew VMAX,Fusion Strike,50.00,https://liga/m\n"
            "Lugia V,Silver Tempest,52.00,https://liga/l\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LIGA_OFFERS_SOURCE", "csv")
        monkeypatch.setenv("LIGA_OFFERS_CSV", str(csv_path))
        comparisons = main_module.run()
        names = {c.card_name for c in comparisons}
        assert "Mew VMAX" in names
        assert "Lugia V" in names


class TestRunPokemontcgMode:
    def test_uses_pokemontcg_when_configured(self, monkeypatch, tmp_reports):
        from src.collectors import pokemontcg

        fetched_queries = []

        def fake_fetch_price(name, set_, **kwargs):
            fetched_queries.append((name, set_))
            return pokemontcg.PokemonTCGResult(
                card_name=name,
                set_name=set_,
                card_number="1",
                price_usd=20.0,
                url=f"https://tcg/{name}",
                variant="holofoil",
            )

        monkeypatch.setattr(
            "src.collectors.pokemontcg.fetch_price", fake_fetch_price
        )
        monkeypatch.setenv("LIGA_TCG_SOURCE", "pokemontcg")
        comparisons = main_module.run()
        # Deve ter chamado a API para cada oferta Liga.
        assert len(fetched_queries) >= 1
        # Pricing veio da API mockada (20 USD * 5.20 = 104 BRL).
        tcg_prices = {round(c.price_tcg_brl, 2) for c in comparisons}
        assert tcg_prices == {104.00}


class TestRunErrorPaths:
    def test_unknown_offer_source_raises(self, monkeypatch, tmp_reports):
        monkeypatch.setenv("LIGA_OFFERS_SOURCE", "ftp")
        with pytest.raises(ValueError, match="Source desconhecido"):
            main_module.run()

    def test_unknown_tcg_source_raises(self, monkeypatch, tmp_reports):
        monkeypatch.setenv("LIGA_TCG_SOURCE", "ftp")
        with pytest.raises(ValueError, match="Source desconhecido"):
            main_module.run()

    def test_missing_liga_csv_raises_with_path(self, monkeypatch, tmp_path, tmp_reports):
        monkeypatch.setenv("LIGA_OFFERS_SOURCE", "csv")
        monkeypatch.setenv("LIGA_OFFERS_CSV", str(tmp_path / "nao_existe.csv"))
        with pytest.raises(FileNotFoundError, match="nao_existe.csv"):
            main_module.run()
