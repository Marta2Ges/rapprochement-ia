"""Deterministic matching between a bank statement and a ledger.

Design rule: the matching is plain, testable code. No AI decides whether two lines match.
The AI layer (see explain.py) only *explains* the breaks that this module has already found.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from .models import Break, BreakKind, Line

DATE_TOLERANCE_DAYS = 3        # max gap for a normal match (value dates differ slightly)
TIMING_WINDOW_DAYS = 30        # beyond tolerance but within this window: timing difference
DESCRIPTION_THRESHOLD = 0.6    # minimum text similarity when there is no common reference
BANK_CHARGE_KEYWORDS = ("frais", "commission", "interet", "fees", "interest")


# ----------------------------------------------------------------------------- helpers
def normalize(text: str) -> str:
    """Lowercase, remove accents and punctuation: 'Café  des Arts!' -> 'cafe des arts'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def _same_reference(bank: Line, ledger: Line) -> bool:
    return bool(bank.reference) and bank.reference == ledger.reference


def _days_apart(bank: Line, ledger: Line) -> int:
    return abs((bank.date - ledger.date).days)


def _score(bank: Line, ledger: Line) -> float:
    """Higher = better candidate. Used to pick the best pair when several are possible."""
    return (
        (1.0 if _same_reference(bank, ledger) else 0.0)
        + similarity(bank.description, ledger.description)
        - 0.01 * _days_apart(bank, ledger)
    )


def _is_transposition(a: Decimal, b: Decimal) -> bool:
    """True when two different amounts use the same digits (e.g. 2'040.00 vs 2'400.00)."""
    digits_a = f"{abs(a):.2f}".replace(".", "")
    digits_b = f"{abs(b):.2f}".replace(".", "")
    return a != b and sorted(digits_a) == sorted(digits_b)


def _is_bank_charge(line: Line) -> bool:
    text = normalize(line.description)
    return any(keyword in text for keyword in BANK_CHARGE_KEYWORDS)


# ----------------------------------------------------------------------------- result
@dataclass
class ReconciliationResult:
    bank_total: Decimal
    ledger_total: Decimal
    matched: list[tuple[Line, Line]] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)

    @property
    def difference(self) -> Decimal:
        """What we need to explain: bank total minus ledger total."""
        return self.bank_total - self.ledger_total

    @property
    def explained(self) -> Decimal:
        return sum((b.impact for b in self.breaks), Decimal("0.00"))

    @property
    def is_fully_explained(self) -> bool:
        return self.difference == self.explained

    def count_by_kind(self) -> dict[BreakKind, int]:
        counts: dict[BreakKind, int] = {}
        for brk in self.breaks:
            counts[brk.kind] = counts.get(brk.kind, 0) + 1
        return counts


# ----------------------------------------------------------------------------- matching
def _greedy_pass(bank_left: list[Line], ledger_left: list[Line], accept) -> list[tuple[Line, Line]]:
    """Pair lines that satisfy `accept`, best score first. Consumes the matched lines."""
    candidates = [
        (-_score(b, l), b.row, l.row, b, l)
        for b in bank_left
        for l in ledger_left
        if accept(b, l)
    ]
    candidates.sort(key=lambda c: c[:3])  # best score first, then file order: deterministic
    used_bank: set[int] = set()
    used_ledger: set[int] = set()
    pairs = []
    for _, _, _, bank, ledger in candidates:
        if bank.row in used_bank or ledger.row in used_ledger:
            continue
        used_bank.add(bank.row)
        used_ledger.add(ledger.row)
        pairs.append((bank, ledger))
    bank_left[:] = [b for b in bank_left if b.row not in used_bank]
    ledger_left[:] = [l for l in ledger_left if l.row not in used_ledger]
    return pairs


def reconcile(
    bank_lines: list[Line],
    ledger_lines: list[Line],
    *,
    date_tolerance: int = DATE_TOLERANCE_DAYS,
    timing_window: int = TIMING_WINDOW_DAYS,
    description_threshold: float = DESCRIPTION_THRESHOLD,
) -> ReconciliationResult:
    bank_left = list(bank_lines)
    ledger_left = list(ledger_lines)
    breaks: list[Break] = []

    def looks_alike(b: Line, l: Line) -> bool:
        return _same_reference(b, l) or similarity(b.description, l.description) >= description_threshold

    # Pass 1 - exact: same amount, dates close, same reference or similar text.
    matched = _greedy_pass(
        bank_left,
        ledger_left,
        lambda b, l: b.amount == l.amount and _days_apart(b, l) <= date_tolerance and looks_alike(b, l),
    )

    # Pass 2 - timing: same amount but dates further apart (payment delay, late booking).
    for bank, ledger in _greedy_pass(
        bank_left,
        ledger_left,
        lambda b, l: b.amount == l.amount
        and date_tolerance < _days_apart(b, l) <= timing_window
        and looks_alike(b, l),
    ):
        breaks.append(
            Break("", BreakKind.TIMING_DIFFERENCE, bank, ledger, Decimal("0.00"),
                  {"days": _days_apart(bank, ledger)})
        )

    # Pass 3 - amount mismatch: same (non-empty) reference but different amounts.
    for bank, ledger in _greedy_pass(
        bank_left,
        ledger_left,
        lambda b, l: _same_reference(b, l) and b.amount != l.amount and _days_apart(b, l) <= timing_window,
    ):
        breaks.append(
            Break("", BreakKind.AMOUNT_MISMATCH, bank, ledger, bank.amount - ledger.amount,
                  {"difference": bank.amount - ledger.amount,
                   "transposition": _is_transposition(bank.amount, ledger.amount)})
        )

    # Leftovers on the bank side: duplicate, bank charge, or unknown operation.
    matched_bank_keys = {
        (b.date, b.amount, normalize(b.description), b.reference): b for b, _ in matched
    }
    for bank in bank_left:
        key = (bank.date, bank.amount, normalize(bank.description), bank.reference)
        if key in matched_bank_keys:
            kind, detail = BreakKind.POSSIBLE_DUPLICATE, {"original_row": matched_bank_keys[key].row}
        elif _is_bank_charge(bank):
            kind, detail = BreakKind.BANK_CHARGE_NOT_BOOKED, {}
        else:
            kind, detail = BreakKind.MISSING_IN_LEDGER, {}
        breaks.append(Break("", kind, bank, None, bank.amount, detail))

    # Leftovers on the ledger side: booked but not (yet) on the statement.
    # A payment booked in the last days of the period is normally just "in transit" (cut-off).
    period_end = max((l.date for l in bank_lines), default=None)
    for ledger in ledger_left:
        near_end = period_end is not None and (period_end - ledger.date).days <= date_tolerance
        breaks.append(
            Break("", BreakKind.MISSING_IN_BANK, None, ledger, -ledger.amount, {"near_period_end": near_end})
        )

    breaks.sort(key=lambda b: (_break_date(b), b.kind.value))
    for index, brk in enumerate(breaks, start=1):
        brk.id = f"B{index:03d}"

    return ReconciliationResult(
        bank_total=sum((l.amount for l in bank_lines), Decimal("0.00")),
        ledger_total=sum((l.amount for l in ledger_lines), Decimal("0.00")),
        matched=matched,
        breaks=breaks,
    )


def _break_date(brk: Break) -> date:
    return (brk.bank or brk.ledger).date
