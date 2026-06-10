"""Coletor de ofertas da Liga Pokemon.

Modos suportados:
- ``mock`` : dados em data/liga_offers_mock.json (default; CI e testes).
- ``csv``  : le um CSV exportado/curado manualmente (ou gerado pelo
  coletor ao vivo). Caminho default em data/liga_offers.csv,
  sobrescrevivel via env var ``LIGA_OFFERS_CSV`` ou parametro ``csv_path``.
- ``live`` : coleta AO VIVO do site com Chrome headful (patchright).
  Requer env var ``LIGA_SETS`` com os codigos de set (ex.: "PRE,SSP").
  Implementacao em src/collectors/liga_live.py. Tambem disponivel via
  CLI dedicada: ``python src/collect_liga_live.py --sets PRE``.
- ``http`` : stub historico. Liga bloqueia clientes nao-browser (403);
  urllib puro nunca vai funcionar. Use ``live`` (browser real) ou ``csv``.

Formato esperado do CSV (header obrigatorio):
    card_name,set_name,price_brl,url[,condition,seller,card_number]

`condition`, `seller` e `card_number` opcionais. Linhas em branco e
linhas iniciadas por ``#`` sao ignoradas. Precos invalidos sao puladas
com aviso no logger, sem matar o pipeline.
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
MOCK_DATA_PATH = DATA_DIR / "liga_offers_mock.json"
DEFAULT_CSV_PATH = DATA_DIR / "liga_offers.csv"

CSV_REQUIRED_COLUMNS = {"card_name", "set_name", "price_brl", "url"}


@dataclass
class LigaOffer:
    card_name: str
    set_name: str
    price_brl: float
    url: str
    condition: str = "NM"
    seller: str = ""
    card_number: str = ""  # numero da carta no set (ex. "156"); melhora o match


def fetch_offers(
    source: str = "mock", csv_path: str | Path | None = None
) -> list[LigaOffer]:
    if source == "mock":
        return _load_mock()
    if source == "csv":
        path = _resolve_csv_path(csv_path)
        return _load_csv(path)
    if source == "live":
        return _collect_live_from_env()
    if source == "http":
        raise NotImplementedError(
            "Scraping HTTP (urllib) da Liga Pokemon nao funciona: o site "
            "bloqueia clientes nao-browser (403/Cloudflare). Use "
            "source='live' (Chrome headful via patchright) ou source='csv'."
        )
    raise ValueError(
        f"Source desconhecido: {source!r}. Use 'mock', 'csv', 'live' ou 'http'."
    )


def _collect_live_from_env() -> list[LigaOffer]:
    """Modo live via env vars (LIGA_SETS obrigatoria, ex.: 'PRE,SSP')."""
    from src.collectors.liga_live import collect_live, resolve_sets

    sets_env = os.environ.get("LIGA_SETS", "").strip()
    if not sets_env:
        raise ValueError(
            "source='live' requer a env var LIGA_SETS com os codigos de set "
            "separados por virgula (ex.: LIGA_SETS=PRE,SSP). Alternativa: "
            "rode a CLI dedicada `python src/collect_liga_live.py --sets PRE`."
        )
    sets = resolve_sets(sets_env.split(","))
    headless = os.environ.get("LIGA_LIVE_HEADLESS", "") == "1"
    resume = os.environ.get("LIGA_LIVE_RESUME", "") == "1"
    return collect_live(sets, headless=headless, resume=resume)


def _resolve_csv_path(explicit: str | Path | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("LIGA_OFFERS_CSV")
    if env:
        return Path(env)
    return DEFAULT_CSV_PATH


def _load_mock() -> list[LigaOffer]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as fp:
        raw = json.load(fp)
    return [LigaOffer(**item) for item in raw]


def _load_csv(path: Path) -> list[LigaOffer]:
    if not path.exists():
        raise FileNotFoundError(
            f"CSV de ofertas Liga nao encontrado em {path}. "
            "Copie data/liga_offers.example.csv e ajuste."
        )

    offers: list[LigaOffer] = []
    with path.open(encoding="utf-8", newline="") as fp:
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
                price = float((row["price_brl"] or "").strip())
            except ValueError:
                logger.warning(
                    "Linha %d em %s ignorada: preco invalido %r",
                    line_no,
                    path,
                    row.get("price_brl"),
                )
                continue
            if price <= 0:
                logger.warning(
                    "Linha %d em %s ignorada: preco nao positivo %r",
                    line_no,
                    path,
                    row.get("price_brl"),
                )
                continue
            offers.append(
                LigaOffer(
                    card_name=(row["card_name"] or "").strip(),
                    set_name=(row["set_name"] or "").strip(),
                    price_brl=price,
                    url=(row["url"] or "").strip(),
                    condition=(row.get("condition") or "NM").strip() or "NM",
                    seller=(row.get("seller") or "").strip(),
                    card_number=(row.get("card_number") or "").strip(),
                )
            )
    return offers
