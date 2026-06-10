"""CLI do coletor AO VIVO da Liga Pokemon.

Comando unico que faz tudo: abre o Chrome (janela visivel), coleta as
ofertas EN+NM dos sets pedidos, salva o data/liga_offers.csv (formato que
o pipeline e o scanner integrado ja leem) e roda o relatorio completo
(precos TCGplayer via pokemontcg.io + margem + reports/).

Uso tipico:

    # scan completo de um set (Chrome abre na tela — nao feche a janela):
    .venv\\Scripts\\python.exe src\\collect_liga_live.py --sets PRE

    # varios sets:
    .venv\\Scripts\\python.exe src\\collect_liga_live.py --sets PRE SSP JTG

    # smoke rapido (so as primeiras 25 cartas da listagem):
    .venv\\Scripts\\python.exe src\\collect_liga_live.py --sets PRE --max-cards 25

    # retomar um scan que caiu no meio:
    .venv\\Scripts\\python.exe src\\collect_liga_live.py --sets PRE --resume

    # so coletar (sem rodar o relatorio TCG no final):
    .venv\\Scripts\\python.exe src\\collect_liga_live.py --sets PRE --no-report

Sets fora da lista conhecida: --sets "XYZ=Nome Do Set Em Ingles".
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.collectors.liga_live import (
    DEFAULT_CSV_PATH,
    DEFAULT_STATE_PATH,
    ED_SETS,
    LigaBlockedError,
    LigaDomChangedError,
    collect_live,
    resolve_sets,
    write_offers_csv,
)


def main() -> int:
    # Console Windows pode estar em cp1252; nomes de carta tem acento.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Coletor ao vivo da Liga Pokemon (Chrome headful + patchright).",
        epilog="Sets conhecidos: " + ", ".join(sorted(ED_SETS)),
    )
    parser.add_argument(
        "--sets", nargs="+", required=True,
        help="codigos de set da Liga (ex.: PRE SSP) ou CODIGO=Nome Em Ingles",
    )
    parser.add_argument(
        "--max-cards", type=int, default=None,
        help="limita as N primeiras cartas de cada set (smoke/teste)",
    )
    parser.add_argument(
        "--min-price", type=float, default=50.0,
        help="piso de preco em R$ p/ pre-filtro da listagem (default 50)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="retoma do checkpoint (data/liga_live_state.json) em vez de recomecar",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Chrome invisivel (AVISO: o Cloudflare costuma barrar headless; "
             "o padrao headful e o que funciona)",
    )
    parser.add_argument(
        "--csv", type=Path, default=DEFAULT_CSV_PATH,
        help=f"onde salvar o CSV de ofertas (default {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="so coleta e salva o CSV; nao roda o relatorio TCG no final",
    )
    args = parser.parse_args()

    try:
        sets = resolve_sets(args.sets)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Sets: {', '.join(f'{c} ({n})' for c, n in sets.items())}")
    print("O Chrome vai abrir numa janela visivel — NAO FECHE a janela.")
    print(f"Checkpoint: {DEFAULT_STATE_PATH} (use --resume se o scan cair)")

    try:
        offers = collect_live(
            sets,
            min_price=args.min_price,
            max_cards_per_set=args.max_cards,
            headless=args.headless,
            resume=args.resume,
        )
    except (LigaBlockedError, LigaDomChangedError) as exc:
        print(f"\nFALHA HONESTA: {exc}", file=sys.stderr)
        print("Nenhum preco foi inventado. Veja a evidencia em data/debug/.",
              file=sys.stderr)
        return 2

    if not offers:
        print("\nNenhuma oferta EN+NM coletada (nada acima do piso?). "
              "CSV nao atualizado.")
        return 1

    csv_path = write_offers_csv(offers, args.csv)
    print(f"\n{len(offers)} ofertas EN+NM salvas em {csv_path}")

    if args.no_report:
        print("(--no-report: pulei o relatorio TCG; rode depois com "
              "LIGA_OFFERS_SOURCE=csv LIGA_TCG_SOURCE=pokemontcg python src/main.py)")
        return 0

    print("\nRodando o relatorio (precos TCGplayer via pokemontcg.io)...")
    os.environ["LIGA_OFFERS_SOURCE"] = "csv"
    os.environ["LIGA_OFFERS_CSV"] = str(csv_path)
    os.environ.setdefault("LIGA_TCG_SOURCE", "pokemontcg")
    from src.main import run
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
