"""CSV loading with Swiss-friendly parsing (1'250.00, 31.12.2026, ...)."""
from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Line

REQUIRED_COLUMNS = {"date", "description", "amount"}
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")
CENTS = Decimal("0.01")


def parse_date(raw: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date '{raw}' (expected YYYY-MM-DD or DD.MM.YYYY)")


def parse_amount(raw: str) -> Decimal:
    cleaned = (
        raw.strip().replace("'", "").replace("\u2019", "").replace(" ", "").replace(",", ".")
    )
    try:
        return Decimal(cleaned).quantize(CENTS)
    except InvalidOperation as exc:
        raise ValueError(f"unrecognised amount '{raw}'") from exc


def load_lines(path: str | Path, source: str) -> list[Line]:
    """Read a CSV file with columns date, description, amount and an optional reference."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        lines = []
        for row_number, row in enumerate(reader, start=2):
            try:
                lines.append(
                    Line(
                        source=source,
                        row=row_number,
                        date=parse_date(row["date"]),
                        description=(row["description"] or "").strip(),
                        amount=parse_amount(row["amount"]),
                        reference=(row.get("reference") or "").strip(),
                    )
                )
            except ValueError as exc:
                raise ValueError(f"{path}, line {row_number}: {exc}") from exc
    return lines
