"""Coletor de precos de referencia do TCGplayer (em USD).

Modos suportados:
- ``mock``  : dados em data/tcgplayer_prices_mock.json (default; usado em
  testes e smoke do CI).
- ``csv``   : le um CSV exportado/curado manualmente. Caminho default em
  data/tcgplayer_prices.csv, sobrescrevivel via env var
  ``LIGA_TCG_CSV`` ou parametro ``csv_path``.
- ``api``   : stub. Integracao oficial exige credenciais e fica para
  depois do MVP.

Formato esperado do CSV (header obrigatorio):
    card_name,set_name,market_price_usd[,url]

`url` e opcional; ausente vira string vazia. Linhas em branco e linhas
iniciadas por ``#`` sao ignoradas. Precos invalidos sao puladas com aviso
no logger (sem matar o pipeline).
"""
from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MOCK_DATA_PATH = DATA_DIR / "tcgplayer_prices_mock.json"
DEFAULT_CSV_PATH = DATA_DIR / "tcgplayer_prices.csv"

CSV_REQUIRED_COLUMNS = {"card_name", "set_name", "market_price_usd"}


@dataclass
class TCGReference:
    card_name: str
    set_name: str
    price_usd: float
    url: str = ""


def fetch_reference_prices(
    source: str = "mock", csv_path: str | Path | None = None
) -> list[TCGReference]:
    if source == "mock":
        return _load_mock()
    if source == "csv":
        path = _resolve_csv_path(csv_path)
        return _load_csv(path)
    if source == "api":
        raise NotImplementedError(
            "Integracao com a API do TCGplayer exige credenciais oficiais."
        )
    raise ValueError(
        f"Source desconhecido: {source!r}. Use 'mock', 'csv' ou 'api'."
    )


def _resolve_csv_path(explicit: str | Path | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("LIGA_TCG_CSV")
    if env:
        return Path(env)
    return DEFAULT_CSV_PATH


def _load_mock() -> list[TCGReference]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as fp:
        raw = json.load(fp)
    return [TCGReference(**item) for item in raw]


def _load_csv(path: Path) -> list[TCGReference]:
    if not path.exists():
        raise FileNotFoundError(
            f"CSV de referencia TCGplayer nao encontrado em {path}. "
            "Copie data/tcgplayer_prices.example.csv e ajuste."
        )

    refs: list[TCGReference] = []
    with path.open(encoding="utf-8", newline="") as fp:
        # Ignora linhas de comentario antes do reader processar o header.
        rows = (line for line in fp if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(rows)
        missing = CSV_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"CSV {path} sem colunas obrigatorias: {sorted(missing)}. "
                f"Esperado: {sorted(CSV_REQUIRED_COLUMNS)}."
            )

        for line_no, row in enumerate(reader, start=2):
            try:
                price = float((row["market_price_usd"] or "").strip())
            except ValueError:
                logger.warning(
                    "Linha %d em %s ignorada: preco invalido %r",
                    line_no,
                    path,
                    row.get("market_price_usd"),
                )
                continue
            refs.append(
                TCGReference(
                    card_name=(row["card_name"] or "").strip(),
                    set_name=(row["set_name"] or "").strip(),
                    price_usd=price,
                    url=(row.get("url") or "").strip(),
                )
            )
    return refs
