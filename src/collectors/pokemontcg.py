"""Cliente leve para pokemontcg.io API (HTTP publico, sem auth).

A API expoe precos de mercado TCGplayer indiretamente (via campo
`tcgplayer.prices.<variant>.market`). Aceita query Lucene-like:

    name:"Charizard ex" set.name:"Obsidian Flames"

Para cards com varias versoes no mesmo set (regular, full art, etc),
aceitar `card_number` desambigua. Sem `card_number`, a estrategia
default e pegar a versao com menor `market` (assumindo que o vendedor
da Liga lista a regular, nao a alt art).
"""
from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

API_BASE = "https://api.pokemontcg.io/v2/cards"
DEFAULT_USER_AGENT = "liga-pokemon-scanner/0.1 (https://github.com/matheuscllm-lgtm/liga-pokemon-scanner)"
DEFAULT_TIMEOUT = 15
# Variantes mais comuns ordenadas por preferencia: o "preco padrao" varia
# por raridade. holofoil cobre maioria dos modernos; normal cobre commons.
VARIANT_PRIORITY = ("holofoil", "normal", "reverseHolofoil", "1stEditionHolofoil")


@dataclass
class PokemonTCGResult:
    card_name: str
    set_name: str
    card_number: str
    price_usd: float
    url: str
    variant: str  # qual variante foi escolhida ("holofoil", "normal", ...)


def fetch_price(
    card_name: str,
    set_name: str,
    card_number: str | None = None,
    variant: str | None = None,
    price_field: str = "market",
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT,
    delay_after: float = 1.0,
) -> PokemonTCGResult | None:
    """Busca preco TCGplayer via pokemontcg.io.

    Retorna ``None`` se a API nao tiver o card ou se o preco nao estiver
    disponivel. Aplica ``delay_after`` segundos apos o request para
    respeitar rate limits da API publica (default 1s).
    """
    query = f'name:"{card_name}" set.name:"{set_name}"'
    if card_number:
        query = f'{query} number:"{card_number}"'

    params = urllib.parse.urlencode({"q": query, "pageSize": 10})
    url = f"{API_BASE}?{params}"
    headers = {"User-Agent": user_agent, "Accept": "application/json"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            import json as _json
            payload = _json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("pokemontcg.io falhou para %r/%r: %s", card_name, set_name, exc)
        return None
    finally:
        if delay_after > 0:
            time.sleep(delay_after)

    cards = payload.get("data", [])
    if not cards:
        return None

    chosen, chosen_variant, chosen_price = _pick_best(cards, variant, price_field)
    if chosen is None:
        return None

    return PokemonTCGResult(
        card_name=chosen["name"],
        set_name=chosen["set"]["name"],
        card_number=str(chosen.get("number", "")),
        price_usd=chosen_price,
        url=(chosen.get("tcgplayer") or {}).get("url", ""),
        variant=chosen_variant,
    )


def _pick_best(
    cards: list[dict],
    variant: str | None,
    price_field: str,
) -> tuple[dict | None, str, float]:
    """Escolhe a tupla (card, variante, preco) com menor `market`.

    Se ``variant`` for fornecido, restringe a essa variante. Senao,
    percorre VARIANT_PRIORITY e pega a primeira que tiver preco.
    """
    best_card = None
    best_variant = ""
    best_price = float("inf")
    variants_to_try = [variant] if variant else list(VARIANT_PRIORITY)

    for card in cards:
        prices = (card.get("tcgplayer") or {}).get("prices") or {}
        for v in variants_to_try:
            entry = prices.get(v)
            if not entry:
                continue
            value = entry.get(price_field)
            if not isinstance(value, (int, float)):
                continue
            if value < best_price:
                best_price = float(value)
                best_card = card
                best_variant = v
            break  # ja pegou a variante prioritaria desse card

    if best_card is None:
        return None, "", 0.0
    return best_card, best_variant, best_price
