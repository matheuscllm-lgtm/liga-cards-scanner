"""Entrada do scanner. Roda o pipeline e gera CSV + JSON em reports/."""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Permite executar diretamente com `python src/main.py` sem instalar como pacote.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import os

from src.collectors.liga_pokemon import fetch_offers
from src.collectors.tcgplayer import fetch_reference_prices
from src.matching.card_matcher import Comparison, match_cards
from src.pricing.currency import get_exchange_rate
from src.pricing.margin import MIN_MARGIN_PERCENT, MIN_PRICE_BRL

REPORTS_DIR = _PROJECT_ROOT / "reports"


def run() -> list[Comparison]:
    rate = get_exchange_rate()
    liga_source = os.environ.get("LIGA_OFFERS_SOURCE", "mock")
    liga = fetch_offers(source=liga_source)
    tcg_source = os.environ.get("LIGA_TCG_SOURCE", "mock")
    queries = (
        [(o.card_name, o.set_name) for o in liga]
        if tcg_source == "pokemontcg"
        else None
    )
    tcg = fetch_reference_prices(source=tcg_source, queries=queries)
    comparisons = match_cards(liga, tcg, rate)

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _write_json(comparisons, REPORTS_DIR / f"report_{stamp}.json")
    _write_csv(comparisons, REPORTS_DIR / f"report_{stamp}.csv")
    _write_xlsx(comparisons, REPORTS_DIR / f"report_{stamp}.xlsx")
    _print_summary(comparisons, rate)
    return comparisons


def _write_json(items: list[Comparison], path: Path) -> None:
    payload = [asdict(item) for item in items]
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def _write_csv(items: list[Comparison], path: Path) -> None:
    if not items:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(asdict(items[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))


def _write_xlsx(items: list[Comparison], path: Path) -> None:
    try:
        from src.reporting.xlsx import write_xlsx
        write_xlsx(items, path)
    except ImportError:
        print("[aviso] openpyxl ausente; pulando geracao do XLSX. Rode: pip install openpyxl")


def _print_summary(items: list[Comparison], rate: float) -> None:
    approved = [c for c in items if c.status == "approved"]
    print(f"Câmbio USD->BRL utilizado: {rate:.4f}")
    print(f"Ofertas comparadas: {len(items)}")
    print(
        f"Aprovadas (margem bruta >= {MIN_MARGIN_PERCENT:.0f}% e "
        f"preço >= R${MIN_PRICE_BRL:.0f}): {len(approved)}"
    )
    print()
    header = (
        f"{'Card':<32} {'Set':<22} {'Liga R$':>10} "
        f"{'TCG R$':>10} {'Margem':>8}  Status"
    )
    print(header)
    print("-" * len(header))
    for c in items:
        print(
            f"{c.card_name[:31]:<32} {c.set_name[:21]:<22} "
            f"{c.price_liga_brl:>10.2f} {c.price_tcg_brl:>10.2f} "
            f"{c.margin_percent:>7.2f}%  {c.status}"
        )


if __name__ == "__main__":
    run()
