"""Coletor de preços de referência do TCGplayer (em USD).

Igual ao coletor da Liga, opera por mock até a integração oficial (API
TCGplayer) estar configurada com credenciais.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MOCK_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "tcgplayer_prices_mock.json"
)


@dataclass
class TCGReference:
    card_name: str
    set_name: str
    price_usd: float
    url: str


def fetch_reference_prices(source: str = "mock") -> list[TCGReference]:
    if source == "mock":
        return _load_mock()
    raise NotImplementedError(
        "Integração com a API do TCGplayer exige credenciais oficiais."
    )


def _load_mock() -> list[TCGReference]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as fp:
        raw = json.load(fp)
    return [TCGReference(**item) for item in raw]
