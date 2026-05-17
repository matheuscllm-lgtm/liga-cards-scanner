"""Coletor de ofertas da Liga Pokémon.

Implementa carregamento via mock por padrão. Scraping ao vivo é stub
intencional: precisa respeitar robots.txt, rate limits e termos de uso
antes de ser ligado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MOCK_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "liga_offers_mock.json"
)


@dataclass
class LigaOffer:
    card_name: str
    set_name: str
    price_brl: float
    url: str
    condition: str = "NM"


def fetch_offers(source: str = "mock") -> list[LigaOffer]:
    if source == "mock":
        return _load_mock()
    raise NotImplementedError(
        "Scraping ao vivo da Liga Pokémon ainda não foi implementado. "
        "Use source='mock' até o coletor respeitar robots.txt e rate limits."
    )


def _load_mock() -> list[LigaOffer]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as fp:
        raw = json.load(fp)
    return [LigaOffer(**item) for item in raw]
