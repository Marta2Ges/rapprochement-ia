import random
import unittest
from datetime import date, timedelta
from decimal import Decimal as D

from recon.matcher import normalize, reconcile, similarity
from recon.models import BreakKind, Line


def bank(row, day, desc, amount, ref=""):
    return Line("bank", row, day, desc, D(amount), ref)


def ledger(row, day, desc, amount, ref=""):
    return Line("ledger", row, day, desc, D(amount), ref)


D1 = date(2026, 9, 10)


class TextHelpersTest(unittest.TestCase):
    def test_normalize_strips_accents_and_punctuation(self):
        self.assertEqual(normalize("  Café  des Arts! "), "cafe des arts")

    def test_similarity_ignores_case_and_accents(self):
        self.assertGreater(similarity("VIR RECU ATELIER LUMIÈRE", "vir recu atelier lumiere"), 0.99)


class MatchingTest(unittest.TestCase):
    def test_exact_match_with_small_date_gap(self):
        result = reconcile([bank(2, D1 + timedelta(days=2), "VIR X", "100.00", "R1")],
                           [ledger(2, D1, "Paiement X", "100.00", "R1")])
        self.assertEqual(len(result.matched), 1)
        self.assertEqual(result.breaks, [])

    def test_match_by_description_when_no_reference(self):
        result = reconcile([bank(2, D1, "VIR RECU ATELIER LUMIERE", "500.00")],
                           [ledger(2, D1, "Encaissement client Atelier Lumière", "500.00")])
        self.assertEqual(len(result.matched), 1)

    def test_same_amount_but_unrelated_text_is_not_matched(self):
        result = reconcile([bank(2, D1, "ZZZZ QQQQ", "500.00")], [ledger(2, D1, "Loyer", "500.00")])
        self.assertEqual(result.matched, [])
        self.assertEqual({b.kind for b in result.breaks},
                         {BreakKind.MISSING_IN_LEDGER, BreakKind.MISSING_IN_BANK})

    def test_timing_difference(self):
        result = reconcile([bank(2, D1 + timedelta(days=10), "VIR X", "100.00", "R1")],
                           [ledger(2, D1, "Paiement X", "100.00", "R1")])
        self.assertEqual([b.kind for b in result.breaks], [BreakKind.TIMING_DIFFERENCE])
        self.assertEqual(result.breaks[0].detail["days"], 10)
        self.assertEqual(result.breaks[0].impact, D("0.00"))

    def test_amount_mismatch_detects_transposed_digits(self):
        result = reconcile([bank(2, D1, "VIR X", "-2400.00", "R1")], [ledger(2, D1, "Paiement X", "-2040.00", "R1")])
        brk = result.breaks[0]
        self.assertEqual(brk.kind, BreakKind.AMOUNT_MISMATCH)
        self.assertTrue(brk.detail["transposition"])
        self.assertEqual(brk.impact, D("-360.00"))

    def test_amount_mismatch_without_transposition(self):
        result = reconcile([bank(2, D1, "VIR X", "1250.00", "R1")], [ledger(2, D1, "Paiement X", "1300.00", "R1")])
        self.assertFalse(result.breaks[0].detail["transposition"])

    def test_missing_in_ledger(self):
        result = reconcile([bank(2, D1, "VIR RECU REMBOURSEMENT TVA", "1134.80")], [])
        self.assertEqual(result.breaks[0].kind, BreakKind.MISSING_IN_LEDGER)

    def test_bank_charge_not_booked(self):
        result = reconcile([bank(2, D1, "FRAIS DE TENUE DE COMPTE", "-45.00")], [])
        self.assertEqual(result.breaks[0].kind, BreakKind.BANK_CHARGE_NOT_BOOKED)

    def test_missing_in_bank_near_period_end_is_flagged_as_cutoff(self):
        bank_lines = [bank(2, date(2026, 9, 30), "VIR Y", "-10.00", "R9")]
        ledger_lines = [ledger(2, date(2026, 9, 30), "Paiement Z", "-80.00", "R2"),
                        ledger(3, date(2026, 9, 5), "Paiement W", "-60.00", "R3"),
                        ledger(4, date(2026, 9, 30), "Paiement Y", "-10.00", "R9")]
        result = reconcile(bank_lines, ledger_lines)
        flags = {b.ledger.reference: b.detail["near_period_end"] for b in result.breaks}
        self.assertEqual(flags, {"R2": True, "R3": False})

    def test_possible_duplicate(self):
        line = dict(day=D1, desc="VIR EMIS X", amount="-300.00", ref="R1")
        result = reconcile([bank(2, **line), bank(3, **line)], [ledger(2, D1, "Paiement X", "-300.00", "R1")])
        self.assertEqual(len(result.matched), 1)
        self.assertEqual([b.kind for b in result.breaks], [BreakKind.POSSIBLE_DUPLICATE])
        self.assertEqual(result.breaks[0].impact, D("-300.00"))

    def test_break_ids_are_sequential(self):
        result = reconcile([bank(2, D1, "A", "1.00"), bank(3, D1, "B", "2.00")], [])
        self.assertEqual([b.id for b in result.breaks], ["B001", "B002"])


class InvariantTest(unittest.TestCase):
    """Whatever the input, every line is used once and the breaks explain the difference."""

    def test_difference_is_always_fully_explained_on_messy_random_data(self):
        rng = random.Random(7)
        words = ["Atelier", "Garage", "Café", "Studio", "Frais", "Loyer", "Menuiserie"]
        for _ in range(50):
            def make(source, count):
                return [
                    Line(source, row, date(2026, 9, 1) + timedelta(days=rng.randint(0, 40)),
                         " ".join(rng.sample(words, 2)),
                         D(rng.randint(-500, 500)) + D(rng.choice(["0.00", "0.50", "0.25"])),
                         rng.choice(["", "R1", "R2", "R3"]))
                    for row in range(2, 2 + count)
                ]
            bank_lines, ledger_lines = make("bank", rng.randint(0, 25)), make("ledger", rng.randint(0, 25))
            result = reconcile(bank_lines, ledger_lines)
            self.assertTrue(result.is_fully_explained)
            self.assertEqual(len(bank_lines), len(result.matched) + sum(1 for b in result.breaks if b.bank))
            self.assertEqual(len(ledger_lines), len(result.matched) + sum(1 for b in result.breaks if b.ledger))


if __name__ == "__main__":
    unittest.main()
