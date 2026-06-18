"""Casamento entre ofertas Liga e precos de referencia TCGplayer.

Estrategia em tres camadas:
1. Match exato por (card_name, set_name, card_number) normalizados —
   so quando AMBOS os lados informam o numero da carta. E o match mais
   forte: distingue versoes diferentes do mesmo nome no mesmo set
   (ex.: Umbreon ex regular vs Special Illustration Rare na PRE).
2. Match exato pelo par (card_name, set_name) ja normalizado.
3. Match fuzzy via difflib.SequenceMatcher, ponderando nome (0.7) e set
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

FUZZY_MATCH_THRESHOLD = 0.82
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
    card_number: str = ""  # numero da carta no set (ex. "156"); p/ a coluna Carta


def _normalized_key(card_name: str, set_name: str) -> tuple[str, str]:
    return (normalize_card_name(card_name), normalize_set_name(set_name))


def _token_set_similarity(a: str, b: str) -> float:
    """Similaridade por conjunto de tokens (palavras): |interseccao| / max(|A|,|B|).

    Robusta a reordenacao e a um lado ser subconjunto do outro — onde o difflib
    de caracteres falha (ex.: "151" vs "scarlet & violet 151", ou "scarlet violet"
    sem o "&")."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _containment_bonus(a: str, b: str) -> float:
    """Bonus pequeno quando os tokens de um lado sao subconjunto do outro
    (codigo curto contido no nome completo)."""
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and (ta <= tb or tb <= ta):
        return 0.1
    return 0.0


def _field_score(a: str, b: str) -> float:
    """Score de um campo (nome ou set) em [0,~1.1]: media de difflib (erro de
    digitacao) com token-set (reordenacao/subconjunto), mais o bonus de
    containment. Misturar os dois generaliza melhor que difflib puro."""
    diff = difflib.SequenceMatcher(None, a, b).ratio()
    token = _token_set_similarity(a, b)
    return (diff + token) / 2 + _containment_bonus(a, b)


def _combined_score(
    offer_key: tuple[str, str], cand_key: tuple[str, str]
) -> float:
    name_score = _field_score(offer_key[0], cand_key[0])
    set_score = _field_score(offer_key[1], cand_key[1])
    return min(1.0, NAME_WEIGHT * name_score + SET_WEIGHT * set_score)


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
    # Indice por numero (camada 1): so refs que informam card_number.
    index_by_number: dict[tuple[str, str, str], TCGReference] = {
        (*_normalized_key(ref.card_name, ref.set_name),
         getattr(ref, "card_number", "")): ref
        for ref in tcg_references
        if getattr(ref, "card_number", "")
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
        ref = None
        offer_number = getattr(offer, "card_number", "")
        if offer_number:
            ref = index_by_number.get((*offer_key, offer_number))
        if ref is None:
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
                # Numero da carta: prefere o da oferta Liga; cai pro da ref TCG.
                card_number=offer_number or getattr(ref, "card_number", ""),
            )
        )

    comparisons.sort(key=lambda c: c.margin_percent, reverse=True)
    return comparisons
