"""Cálculo de margem de arbitragem e regras de aprovação."""
from __future__ import annotations

MIN_MARGIN_PERCENT = 30.0
MIN_PRICE_BRL = 50.0


def calculate_margin(price_liga_brl: float, price_tcg_brl: float) -> float:
    """Margem BRUTA (%) = ((TCG_BRL - Liga_BRL) / Liga_BRL) * 100.

    Bruta = so a diferenca de preco entre o card na Liga e a referencia
    TCGplayer. NAO embute nenhuma taxa (frete, cartao, IOF, etc.); essas
    o operador calcula por fora, manualmente.
    """
    if price_liga_brl <= 0:
        raise ValueError("Preço da Liga Pokémon precisa ser positivo.")
    return ((price_tcg_brl - price_liga_brl) / price_liga_brl) * 100


def is_approved(
    price_liga_brl: float,
    margin_percent: float,
    min_price: float = MIN_PRICE_BRL,
    min_margin: float = MIN_MARGIN_PERCENT,
) -> bool:
    return price_liga_brl >= min_price and margin_percent >= min_margin
