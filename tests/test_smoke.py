"""Smoke tests: garantem que o pipeline mockado roda ponta a ponta.

Testes unitários específicos (margin, currency, matching, filters) virão
em PRs subsequentes.
"""
import os
import subprocess
import sys
from pathlib import Path

from src.collectors.liga_pokemon import fetch_offers
from src.collectors.tcgplayer import fetch_reference_prices
from src.matching.card_matcher import match_cards

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_runs_with_mock_data():
    offers = fetch_offers()
    refs = fetch_reference_prices()
    comparisons = match_cards(offers, refs, exchange_rate=5.20)

    assert comparisons, "matcher deveria produzir ao menos uma comparação"

    margins = [c.margin_percent for c in comparisons]
    assert margins == sorted(margins, reverse=True), (
        "comparações devem vir ordenadas por margem decrescente"
    )

    assert any(c.status == "approved" for c in comparisons)
    assert any(c.status == "rejected" for c in comparisons)


def test_main_prints_delivery_table_on_cp1252_console():
    """Regressao: console Windows em cp1252 crashava no print final da
    tabela de entrega (emoji 🟢 e '≥' nao existem em cp1252). O guard de
    reconfigure p/ UTF-8 no __main__ do main.py evita o UnicodeEncodeError."""
    env = {
        **os.environ,
        "LIGA_USD_BRL_RATE": "5.20",
        "PYTHONIOENCODING": "cp1252",  # simula o console legado do Windows
    }
    result = subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "src" / "main.py")],
        capture_output=True,
        env=env,
        cwd=_PROJECT_ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "Liga Pok" in result.stdout.decode("utf-8", errors="replace")
