"""Conversao cambial USD -> BRL.

Modos:
- ``LIGA_USD_BRL_RATE=<float>`` (default 5.20): taxa fixa.
- ``LIGA_USD_BRL_RATE=auto``: busca cotacao ao vivo na AwesomeAPI
  (https://economia.awesomeapi.com.br/json/last/USD-BRL). Fallback
  silencioso para DEFAULT_USD_BRL_RATE se a API falhar.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_USD_BRL_RATE = 5.20
LIVE_RATE_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
LIVE_RATE_TIMEOUT = 8
USER_AGENT = "liga-pokemon-scanner/0.1"


def get_exchange_rate() -> float:
    raw = os.environ.get("LIGA_USD_BRL_RATE", "").strip()
    if not raw:
        return DEFAULT_USD_BRL_RATE
    if raw.lower() == "auto":
        rate = _fetch_live_rate()
        if rate is not None:
            return rate
        logger.warning("AwesomeAPI indisponivel; usando fallback %.2f", DEFAULT_USD_BRL_RATE)
        return DEFAULT_USD_BRL_RATE
    try:
        return float(raw)
    except ValueError:
        logger.warning("LIGA_USD_BRL_RATE=%r invalido; usando fallback %.2f", raw, DEFAULT_USD_BRL_RATE)
        return DEFAULT_USD_BRL_RATE


def _fetch_live_rate() -> float | None:
    try:
        req = urllib.request.Request(LIVE_RATE_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=LIVE_RATE_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.warning("AwesomeAPI falhou: %s", exc)
        return None
    entry = payload.get("USDBRL") if isinstance(payload, dict) else None
    if not entry:
        return None
    bid = entry.get("bid")
    try:
        return float(bid)
    except (TypeError, ValueError):
        return None


def convert_usd_to_brl(amount_usd: float, rate: float | None = None) -> float:
    if rate is None:
        rate = get_exchange_rate()
    return round(amount_usd * rate, 2)
