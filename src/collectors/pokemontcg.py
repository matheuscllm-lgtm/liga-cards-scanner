"""Cliente leve para pokemontcg.io API (HTTP publico, sem auth).

A API expoe precos de mercado TCGplayer indiretamente (via campo
`tcgplayer.prices.<variant>.market`). Aceita query Lucene-like:

    name:"Charizard ex" set.name:"Obsidian Flames"

Para cards com varias versoes no mesmo set (regular, full art, etc),
aceitar `card_number` desambigua. Sem `card_number`, a estrategia
default e pegar a versao com menor `market` (assumindo que o vendedor
da Liga lista a regular, nao a alt art).

Robustez:
- Cache local em disco (default 24h TTL) em data/cache/pokemontcg/<sha>.json
  para reduzir hits a API entre execucoes. Desabilita com cache_dir=None.
- Retry com backoff exponencial (1s, 2s, 4s) em TimeoutError, URLError
  com timeout e HTTPError 5xx. Nao retry em 404.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://api.pokemontcg.io/v2/cards"
DEFAULT_USER_AGENT = "liga-pokemon-scanner/0.1 (https://github.com/matheuscllm-lgtm/liga-pokemon-scanner)"
DEFAULT_TIMEOUT = 15
VARIANT_PRIORITY = ("holofoil", "normal", "reverseHolofoil", "1stEditionHolofoil")

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "pokemontcg"
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 1.0


def _clean_secret(value: str | None) -> str | None:
    """Sanitiza um segredo (API key) lido do ambiente — padrao da frota.

    Remove BOM (U+FEFF), zero-width space (U+200B) e espacos/quebras nas
    pontas. Headers HTTP sao codificados em latin-1 pelo urllib; um BOM colado
    por engano na chave (arquivo salvo como UTF-8-with-BOM, copy/paste do site)
    vira ``UnicodeEncodeError: 'latin-1' codec can't encode '\ufeff'`` e derruba
    100% das chamadas. ``str.strip()`` NAO remove BOM (nao e whitespace pra
    Python), entao tratamos explicitamente. Retorna ``None`` se sobrar vazio
    (chave ausente -> nenhum header, requisicao anonima segue funcionando).
    """
    if value is None:
        return None
    cleaned = value.replace("\ufeff", "").replace("\u200b", "").strip()
    return cleaned or None


def _build_headers(user_agent: str) -> dict[str, str]:
    """Monta os headers do request, anexando ``X-Api-Key`` apenas se a chave
    ``POKEMONTCG_API_KEY`` estiver presente (e limpa) no ambiente.

    Sem a chave, retorna so User-Agent + Accept — a API e publica e responde
    anonimamente (rate limit mais apertado). Com a chave, o rate limit sobe.
    """
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    api_key = _clean_secret(os.environ.get("POKEMONTCG_API_KEY"))
    if api_key:
        headers["X-Api-Key"] = api_key
    return headers


@dataclass
class PokemonTCGResult:
    card_name: str
    set_name: str
    card_number: str
    price_usd: float
    url: str
    variant: str


def fetch_price(
    card_name: str,
    set_name: str,
    card_number: str | None = None,
    variant: str | None = None,
    price_field: str = "market",
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT,
    delay_after: float = 1.0,
    cache_dir: str | Path | None = "default",
    cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
) -> PokemonTCGResult | None:
    """Busca preco TCGplayer via pokemontcg.io.

    Retorna ``None`` se a API nao tiver o card ou se o preco nao estiver
    disponivel. Aplica ``delay_after`` segundos apos request real (cache
    hit nao gasta delay).
    """
    query = f'name:"{card_name}" set.name:"{set_name}"'
    if card_number:
        query = f'{query} number:"{card_number}"'

    cache_path = _resolve_cache_path(cache_dir, query)
    payload = _load_cache(cache_path, cache_ttl)
    if payload is None:
        payload = _http_get(query, user_agent, timeout, retry_attempts)
        if payload is None:
            return None
        _save_cache(cache_path, payload)
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


def _http_get(
    query: str, user_agent: str, timeout: float, retry_attempts: int
) -> dict | None:
    params = urllib.parse.urlencode({"q": query, "pageSize": 10})
    url = f"{API_BASE}?{params}"
    headers = _build_headers(user_agent)

    for attempt in range(1, retry_attempts + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == retry_attempts:
                logger.warning("pokemontcg.io HTTP %s para %r: %s", exc.code, query, exc)
                return None
            _sleep_backoff(attempt, query, exc)
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == retry_attempts:
                logger.warning("pokemontcg.io falhou apos %d tentativas para %r: %s", attempt, query, exc)
                return None
            _sleep_backoff(attempt, query, exc)
        except Exception as exc:
            logger.warning("pokemontcg.io erro inesperado para %r: %s", query, exc)
            return None
    return None


def _sleep_backoff(attempt: int, query: str, exc: Exception) -> None:
    delay = DEFAULT_BACKOFF_BASE * (2 ** (attempt - 1))
    logger.info("pokemontcg.io tentativa %d/%d falhou (%s); aguarda %.1fs",
                attempt, DEFAULT_RETRY_ATTEMPTS, type(exc).__name__, delay)
    time.sleep(delay)


def _resolve_cache_path(cache_dir: str | Path | None, query: str) -> Path | None:
    if cache_dir is None:
        return None
    if cache_dir == "default":
        env = os.environ.get("LIGA_POKEMONTCG_CACHE_DIR")
        if env == "":
            return None  # explicitamente desabilitado
        cache_dir = Path(env) if env else DEFAULT_CACHE_DIR
    cache_dir = Path(cache_dir)
    sha = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{sha}.json"


def _load_cache(path: Path | None, ttl: float) -> dict | None:
    if path is None or not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl:
        return None
    try:
        with path.open(encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("cache pokemontcg corrompido em %s: %s", path, exc)
        return None


def _save_cache(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp)
    except OSError as exc:
        logger.warning("nao foi possivel salvar cache pokemontcg em %s: %s", path, exc)


def _pick_best(
    cards: list[dict],
    variant: str | None,
    price_field: str,
) -> tuple[dict | None, str, float]:
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
            break

    if best_card is None:
        return None, "", 0.0
    return best_card, best_variant, best_price
