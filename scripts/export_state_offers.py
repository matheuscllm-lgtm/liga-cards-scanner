"""Exporta as ofertas do checkpoint (data/liga_live_state.json) pro CSV canonico.

Uso: entrega PARCIAL de um scan pausado — o collect_liga_live.py so escreve o
CSV no fim do run; quando o operador pede resultados parciais, as ofertas ja
coletadas moram no checkpoint. Reusa LigaOffer + write_offers_csv do proprio
coletor (mesmo formato, mesmo header), nunca monta formato proprio.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.collectors.liga_live import DEFAULT_CSV_PATH, DEFAULT_STATE_PATH, write_offers_csv
from src.collectors.liga_pokemon import LigaOffer


def main() -> int:
    state = json.loads(Path(DEFAULT_STATE_PATH).read_text(encoding="utf-8"))
    offers: list[LigaOffer] = []
    for set_code, set_state in state.get("sets", {}).items():
        for card_state in set_state.get("cards", {}).values():
            raw = card_state.get("offer")
            if card_state.get("status") == "ok" and raw:
                offers.append(LigaOffer(**raw))
    if not offers:
        print("Nenhuma oferta 'ok' no checkpoint — nada exportado.", file=sys.stderr)
        return 1
    path = write_offers_csv(offers, DEFAULT_CSV_PATH)
    print(f"{len(offers)} ofertas exportadas do checkpoint para {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
