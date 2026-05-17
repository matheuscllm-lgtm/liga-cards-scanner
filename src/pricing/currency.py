"""Conversão cambial USD -> BRL com taxa configurável."""
from __future__ import annotations

import os

# Taxa fallback usada quando não há fonte ao vivo configurada. Pode ser
# sobrescrita pela variável de ambiente LIGA_USD_BRL_RATE para manter os
# relatórios determinísticos durante testes e CI.
DEFAULT_USD_BRL_RATE = 5.20


def get_exchange_rate() -> float:
    raw = os.environ.get("LIGA_USD_BRL_RATE")
    if raw:
        return float(raw)
    return DEFAULT_USD_BRL_RATE


def convert_usd_to_brl(amount_usd: float, rate: float | None = None) -> float:
    if rate is None:
        rate = get_exchange_rate()
    return round(amount_usd * rate, 2)
