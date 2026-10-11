"""Generate FULLY SYNTHETIC data: a month of ledger entries and the matching bank statement,
with a few realistic anomalies injected on purpose.

Companies are fictitious. Never use real client or bank data in this project.

Run:  python scripts/generate_sample_data.py
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SEED = 2026
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MONTH_START = date(2026, 9, 1)

CUSTOMERS = ["Atelier Lumière", "Cabinet Rive Droite", "Boutique du Lac", "Studio Pixel",
             "Menuiserie Alpine", "Café des Arts", "Agence Horizon", "Librairie Saint-Antoine",
             "Fleuriste Les Pivoines", "Garage du Salève", "Cabinet Vétérinaire du Parc", "Atelier Cobalt"]
SUPPLIERS = ["Papeterie du Rhône", "Services Informatiques Léman", "Imprimerie Mont-Blanc",
             "Énergie Genevoise Pro", "Nettoyage Express Sàrl", "Assurances Helvétia Plus",
             "Transports Jura", "Mobilier Bureau Sàrl", "Télécom Arve", "Comptoir des Fournitures",
             "Logistique Lac Léman", "Maintenance Technique SA", "Matériel Pro Genève", "Conseil & Gestion Sàrl"]


def dec(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def build_ledger(rng: random.Random) -> list[dict]:
    used: set[Decimal] = set()

    def unique_amount(low: int, high: int) -> Decimal:
        while True:
            amount = dec(Decimal(rng.randrange(low * 100, high * 100, 5)) / 100)
            if amount not in used:
                used.add(amount)
                return amount

    entries = []
    for i, name in enumerate(CUSTOMERS):
        entries.append(dict(date=MONTH_START + timedelta(days=rng.randint(1, 21)), kind="in",
                            description=f"Encaissement client {name}", name=name,
                            amount=unique_amount(900, 9500), reference=f"FC-{2001 + i}"))
    for i, name in enumerate(SUPPLIERS):
        entries.append(dict(date=MONTH_START + timedelta(days=rng.randint(1, 21)), kind="out",
                            description=f"Paiement fournisseur {name}", name=name,
                            amount=-unique_amount(120, 6000), reference=f"FA-{1001 + i}"))
    entries.append(dict(date=date(2026, 9, 1), kind="rent", description="Loyer septembre", name="",
                        amount=dec("-4500.00"), reference="LOYER-2026-09"))
    entries.append(dict(date=date(2026, 9, 25), kind="salary", description="Salaires septembre", name="",
                        amount=dec("-18500.00"), reference="SAL-2026-09"))

    # ---- anomalies injected on purpose (the test suite checks they are all detected) ----
    # 1-2: timing differences (customer pays late, supplier debited late)
    entries[1].update(date=date(2026, 9, 10), bank_offset=14)
    entries[len(CUSTOMERS) + 3].update(date=date(2026, 9, 5), bank_offset=9)
    # 3-4: amount mismatches (customer deducted 50 CHF; digits swapped on a supplier invoice)
    entries[2].update(bank_amount=entries[2]["amount"] - dec("50.00"))
    entries[len(CUSTOMERS) + 7].update(amount=dec("-2040.00"), bank_amount=dec("-2400.00"))
    # 5: a supplier debit appears twice on the bank statement
    entries[len(CUSTOMERS) + 10].update(duplicate=True)
    # 6-7: payments booked at month end but not yet debited by the bank
    for ref, name, amount, day in (("FA-1090", "Transports Jura", "-1860.40", 29),
                                   ("FA-1091", "Logistique Lac Léman", "-742.15", 30)):
        entries.append(dict(date=date(2026, 9, day), kind="out", description=f"Paiement fournisseur {name}",
                            name=name, amount=dec(amount), reference=ref, in_bank=False))
    return entries


def build_bank(rng: random.Random, ledger: list[dict]) -> list[dict]:
    bank = []
    for e in ledger:
        if e.get("in_bank") is False:
            continue
        offset = e.get("bank_offset", rng.randint(0, 2))
        text = {"in": f"VIR RECU {e['name'].upper()}", "out": f"VIR EMIS {e['name'].upper()}",
                "rent": "ORDRE PERMANENT LOYER", "salary": "VIR SALAIRES SEPT 2026"}[e["kind"]]
        row = dict(date=e["date"] + timedelta(days=offset), description=text,
                   amount=e.get("bank_amount", e["amount"]), reference=e["reference"])
        bank.append(row)
        if e.get("duplicate"):
            bank.append(dict(row))
    # bank-only lines: an unknown refund and two bank charges
    bank += [
        dict(date=date(2026, 9, 18), description="VIR RECU REMBOURSEMENT TVA", amount=dec("1134.80"), reference=""),
        dict(date=date(2026, 9, 30), description="FRAIS DE TENUE DE COMPTE", amount=dec("-45.00"), reference=""),
        dict(date=date(2026, 9, 30), description="COMMISSION VIREMENTS INTERNATIONAUX", amount=dec("-23.50"), reference=""),
    ]
    return sorted(bank, key=lambda r: (r["date"], r["description"]))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "description", "amount", "reference"], lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["date"], r["description"])):
            writer.writerow({"date": row["date"].isoformat(), "description": row["description"],
                             "amount": f"{row['amount']:.2f}", "reference": row["reference"]})


def main(data_dir: Path = DATA_DIR) -> None:
    rng = random.Random(SEED)
    ledger = build_ledger(rng)
    bank = build_bank(rng, ledger)
    data_dir.mkdir(exist_ok=True)
    write_csv(data_dir / "ledger.csv", ledger)
    write_csv(data_dir / "bank_statement.csv", bank)
    print(f"{len(ledger)} ledger entries, {len(bank)} bank lines written to {data_dir}")


if __name__ == "__main__":
    main()
