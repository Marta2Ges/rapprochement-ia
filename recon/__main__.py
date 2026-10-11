"""Command line entry point:  python -m recon --bank ... --ledger ... [--llm]"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .explain import DEFAULT_MODEL, KIND_LABELS_FR, explain_all, fmt_chf
from .loader import load_lines
from .matcher import DATE_TOLERANCE_DAYS, reconcile
from .report import write_csv, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m recon",
        description="Rapprochement bancaire : relevé bancaire vs comptabilité.",
    )
    parser.add_argument("--bank", required=True, help="CSV du relevé bancaire")
    parser.add_argument("--ledger", required=True, help="CSV de la comptabilité")
    parser.add_argument("--out", default="output", help="dossier de sortie (défaut : output)")
    parser.add_argument("--date-tolerance", type=int, default=DATE_TOLERANCE_DAYS,
                        help=f"écart de dates toléré en jours (défaut : {DATE_TOLERANCE_DAYS})")
    parser.add_argument("--llm", action="store_true",
                        help="reformuler les explications avec un LLM (nécessite ANTHROPIC_API_KEY)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="modèle LLM à utiliser avec --llm")
    return parser


def _make_llm_client():
    """Return an Anthropic client, or None (with a clear message) if it cannot be created."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  --llm demandé mais ANTHROPIC_API_KEY est absente : explications par règles.", file=sys.stderr)
        return None
    try:
        import anthropic
    except ImportError:
        print("⚠️  Paquet 'anthropic' absent (pip install -r requirements-llm.txt) : explications par règles.",
              file=sys.stderr)
        return None
    return anthropic.Anthropic()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bank = load_lines(args.bank, "bank")
        ledger = load_lines(args.ledger, "ledger")
    except (OSError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    result = reconcile(bank, ledger, date_tolerance=args.date_tolerance)
    explanations = explain_all(result.breaks, client=_make_llm_client() if args.llm else None, model=args.model)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_markdown(result, explanations, out / "report.md")
    write_csv(result, explanations, out / "breaks.csv")

    print(f"{len(bank)} lignes bancaires, {len(ledger)} écritures comptables")
    print(f"{len(result.matched)} rapprochées automatiquement, {len(result.breaks)} écarts :")
    for kind, count in sorted(result.count_by_kind().items(), key=lambda kv: kv[0].value):
        print(f"  - {KIND_LABELS_FR[kind]} : {count}")
    status = "OK" if result.is_fully_explained else "ÉCHEC"
    print(f"Contrôle (différence {fmt_chf(result.difference)} expliquée par les écarts) : {status}")
    print(f"Rapports écrits dans {out}/")
    return 0 if result.is_fully_explained else 2


if __name__ == "__main__":
    raise SystemExit(main())
