"""Casamento entre ofertas Liga e preços de referência TCGplayer."""
from __future__ import annotations

from dataclasses import dataclass

from src.collectors.liga_pokemon import LigaOffer
from src.collectors.tcgplayer import TCGReference
from src.pricing.currency import convert_usd_to_brl
from src.pricing.margin import (
    MIN_MARGIN_PERCENT,
    MIN_PRICE_BRL,
    calculate_margin,
    is_approved,
)


@dataclass
class Comparison:
    card_name: str
    set_name: str
    price_liga_brl: float
    price_tcg_usd: float
    price_tcg_brl: float
    margin_percent: float
    exchange_rate: float
    liga_url: str
    tcg_url: str
    status: str


def _key(card_name: str, set_name: str) -> str:
    return f"{card_name.strip().lower()}|{set_name.strip().lower()}"


def match_cards(
    liga_offers: list[LigaOffer],
    tcg_references: list[TCGReference],
    exchange_rate: float,
    min_price: float = MIN_PRICE_BRL,
    min_margin: float = MIN_MARGIN_PERCENT,
) -> list[Comparison]:
    tcg_by_key = {
        _key(ref.card_name, ref.set_name): ref for ref in tcg_references
    }
    comparisons: list[Comparison] = []
    for offer in liga_offers:
        ref = tcg_by_key.get(_key(offer.card_name, offer.set_name))
        if ref is None:
            continue
        price_tcg_brl = convert_usd_to_brl(ref.price_usd, exchange_rate)
        margin = calculate_margin(offer.price_brl, price_tcg_brl)
        approved = is_approved(offer.price_brl, margin, min_price, min_margin)
        comparisons.append(
            Comparison(
                card_name=offer.card_name,
                set_name=offer.set_name,
                price_liga_brl=offer.price_brl,
                price_tcg_usd=ref.price_usd,
                price_tcg_brl=price_tcg_brl,
                margin_percent=round(margin, 2),
                exchange_rate=exchange_rate,
                liga_url=offer.url,
                tcg_url=ref.url,
                status="approved" if approved else "rejected",
            )
        )
    comparisons.sort(key=lambda c: c.margin_percent, reverse=True)
    return comparisons
