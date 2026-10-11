"""Report writers: a readable Markdown report and a CSV for Excel."""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .explain import KIND_LABELS_FR, PRIORITY_LABELS_FR, PRIORITY_RANK, fmt_chf
from .matcher import ReconciliationResult
from .models import Break, Explanation


def _sorted_breaks(result: ReconciliationResult, explanations: dict[str, Explanation]) -> list[Break]:
    return sorted(
        result.breaks,
        key=lambda b: (PRIORITY_RANK[explanations[b.id].priority], -abs(b.impact), b.id),
    )


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def write_markdown(result: ReconciliationResult, explanations: dict[str, Explanation], path: Path) -> None:
    lines = ["# Rapport de rapprochement bancaire", ""]
    lines += [
        "| Total relevé bancaire | Total comptabilité | Différence à expliquer |",
        "|---:|---:|---:|",
        f"| {fmt_chf(result.bank_total)} | {fmt_chf(result.ledger_total)} | {fmt_chf(result.difference)} |",
        "",
    ]
    if result.is_fully_explained:
        lines.append(
            f"✅ **Contrôle réussi** : les {len(result.breaks)} écarts ci-dessous expliquent exactement "
            f"la différence ({fmt_chf(result.explained)})."
        )
    else:
        lines.append(
            f"⚠️ **Contrôle échoué** : les écarts expliquent {fmt_chf(result.explained)} sur "
            f"{fmt_chf(result.difference)}. Vérifier les données d'entrée."
        )
    lines += ["", f"{len(result.matched)} opérations rapprochées automatiquement.", ""]

    lines += ["## Synthèse par type d'écart", "", "| Type | Nombre | Impact sur la différence |", "|---|---:|---:|"]
    for kind, count in sorted(result.count_by_kind().items(), key=lambda kv: kv[0].value):
        impact = sum((b.impact for b in result.breaks if b.kind is kind), Decimal("0.00"))
        lines.append(f"| {KIND_LABELS_FR[kind]} | {count} | {fmt_chf(impact)} |")

    lines += ["", "## Détail des écarts (triés par priorité)", "",
              "| ID | Priorité | Type | Date | Impact sur la différence | Explication | Action recommandée |",
              "|---|---|---|---|---:|---|---|"]
    for brk in _sorted_breaks(result, explanations):
        exp = explanations[brk.id]
        date_ = (brk.bank or brk.ledger).date.strftime("%d.%m.%Y")
        lines.append(
            f"| {brk.id} | {PRIORITY_LABELS_FR[exp.priority]} | {KIND_LABELS_FR[brk.kind]} | {date_} | "
            f"{fmt_chf(brk.impact)} | {_cell(exp.text)} | {_cell(exp.action)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(result: ReconciliationResult, explanations: dict[str, Explanation], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["id", "priorite", "type", "date_banque", "date_comptabilite", "description",
                         "reference", "impact_chf", "explication", "action", "source_explication"])
        for brk in _sorted_breaks(result, explanations):
            exp = explanations[brk.id]
            line = brk.bank or brk.ledger
            writer.writerow([
                brk.id, exp.priority, brk.kind.value,
                brk.bank.date.isoformat() if brk.bank else "",
                brk.ledger.date.isoformat() if brk.ledger else "",
                line.description, line.reference, brk.impact, exp.text, exp.action, exp.source,
            ])
