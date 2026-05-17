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

from src.collectors.liga_pokemon import fetch_offers
from src.collectors.tcgplayer import fetch_reference_prices
from src.matching.card_matcher import Comparison, match_cards
from src.pricing.currency import get_exchange_rate

REPORTS_DIR = _PROJECT_ROOT / "reports"


def run() -> list[Comparison]:
    rate = get_exchange_rate()
    liga = fetch_offers()
    tcg = fetch_reference_prices()
    comparisons = match_cards(liga, tcg, rate)

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _write_json(comparisons, REPORTS_DIR / f"report_{stamp}.json")
    _write_csv(comparisons, REPORTS_DIR / f"report_{stamp}.csv")
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


def _print_summary(items: list[Comparison], rate: float) -> None:
    approved = [c for c in items if c.status == "approved"]
    print(f"Câmbio USD->BRL utilizado: {rate:.4f}")
    print(f"Ofertas comparadas: {len(items)}")
    print(f"Aprovadas (margem >= 25% e preço >= R$50): {len(approved)}")
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
