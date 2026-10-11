"""Data structures shared across the package."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class BreakKind(str, Enum):
    """Every unmatched or inconsistent item ends up in exactly one of these categories."""

    TIMING_DIFFERENCE = "timing_difference"          # same amount, dates too far apart
    AMOUNT_MISMATCH = "amount_mismatch"              # same reference, different amount
    MISSING_IN_LEDGER = "missing_in_ledger"          # on the bank statement only
    MISSING_IN_BANK = "missing_in_bank"              # in the books only (e.g. payment in transit)
    BANK_CHARGE_NOT_BOOKED = "bank_charge_not_booked"  # bank fees / interest not yet booked
    POSSIBLE_DUPLICATE = "possible_duplicate"        # same bank line appearing twice


@dataclass(frozen=True)
class Line:
    """One transaction, either from the bank statement or from the ledger."""

    source: str          # "bank" or "ledger"
    row: int             # line number in the original CSV (header = line 1)
    date: date
    description: str
    amount: Decimal      # negative = money going out
    reference: str = ""


@dataclass
class Break:
    """A discrepancy found by the matcher."""

    id: str
    kind: BreakKind
    bank: Line | None
    ledger: Line | None
    # Contribution of this break to (bank total - ledger total).
    # The sum of all impacts must equal that difference: this is the safety check.
    impact: Decimal
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Explanation:
    """Human-readable explanation of a break. Never changes the numbers."""

    text: str
    action: str
    priority: str        # "high" | "medium" | "low"
    source: str = "rules"  # "rules" or "llm"
