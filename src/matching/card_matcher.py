"""Casamento entre ofertas Liga e precos de referencia TCGplayer.

Estrategia em duas camadas:
1. Match exato pelo par (card_name, set_name) ja normalizado.
2. Match fuzzy via difflib.SequenceMatcher, ponderando nome (0.7) e set
   (0.3). Aceita se o score combinado >= FUZZY_MATCH_THRESHOLD.

`Comparison.match_score` registra a confianca (1.0 = match exato).
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass

from src.collectors.liga_pokemon import LigaOffer
from src.collectors.tcgplayer import TCGReference
from src.matching.normalization import normalize_card_name, normalize_set_name
from src.pricing.currency import convert_usd_to_brl
from src.pricing.margin import (
    MIN_MARGIN_PERCENT,
    MIN_PRICE_BRL,
    calculate_margin,
    is_approved,
)

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 0.85
NAME_WEIGHT = 0.7
SET_WEIGHT = 0.3


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
    match_score: float = 1.0


def _normalized_key(card_name: str, set_name: str) -> tuple[str, str]:
    return (normalize_card_name(card_name), normalize_set_name(set_name))


def _combined_score(
    offer_key: tuple[str, str], cand_key: tuple[str, str]
) -> float:
    name_score = difflib.SequenceMatcher(None, offer_key[0], cand_key[0]).ratio()
    set_score = difflib.SequenceMatcher(None, offer_key[1], cand_key[1]).ratio()
    return NAME_WEIGHT * name_score + SET_WEIGHT * set_score


def _find_best_fuzzy(
    offer_key: tuple[str, str],
    index: dict[tuple[str, str], TCGReference],
    threshold: float,
) -> tuple[TCGReference | None, float]:
    best_ref: TCGReference | None = None
    best_score = 0.0
    for cand_key, ref in index.items():
        score = _combined_score(offer_key, cand_key)
        if score > best_score:
            best_score = score
            best_ref = ref
    if best_score >= threshold:
        return best_ref, best_score
    return None, best_score


def match_cards(
    liga_offers: list[LigaOffer],
    tcg_references: list[TCGReference],
    exchange_rate: float,
    min_price: float = MIN_PRICE_BRL,
    min_margin: float = MIN_MARGIN_PERCENT,
    fuzzy_threshold: float = FUZZY_MATCH_THRESHOLD,
) -> list[Comparison]:
    index: dict[tuple[str, str], TCGReference] = {
        _normalized_key(ref.card_name, ref.set_name): ref
        for ref in tcg_references
    }

    comparisons: list[Comparison] = []
    for offer in liga_offers:
        if offer.price_brl <= 0:
            # Margem exige preco Liga positivo (ver calculate_margin). Pula
            # em vez de deixar a excecao abortar o pipeline inteiro.
            logger.warning(
                "Oferta %r ignorada: preco Liga nao positivo (%s).",
                offer.card_name,
                offer.price_brl,
            )
            continue
        offer_key = _normalized_key(offer.card_name, offer.set_name)
        score = 1.0
        ref = index.get(offer_key)
        if ref is None:
            ref, score = _find_best_fuzzy(offer_key, index, fuzzy_threshold)
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
                match_score=round(score, 3),
            )
        )

    comparisons.sort(key=lambda c: c.margin_percent, reverse=True)
    return comparisons
