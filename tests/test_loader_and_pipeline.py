import filecmp
import tempfile
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from recon import __main__ as cli
from recon.loader import load_lines, parse_amount, parse_date
from recon.matcher import reconcile
from recon.models import BreakKind
from scripts import generate_sample_data

ROOT = Path(__file__).resolve().parent.parent


class LoaderTest(unittest.TestCase):
    def test_swiss_formats(self):
        self.assertEqual(parse_amount("1'250.50"), D("1250.50"))
        self.assertEqual(parse_amount("-1 250,5"), D("-1250.50"))
        self.assertEqual(parse_date("31.12.2026"), date(2026, 12, 31))
        self.assertEqual(parse_date("2026-12-31"), date(2026, 12, 31))

    def test_error_message_names_the_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "bad.csv")
            path.write_text("date,description,amount\n2026-09-01,ok,10.00\n2026-09-02,bad,abc\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 3"):
                load_lines(path, "bank")

    def test_missing_column_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "bad.csv")
            path.write_text("date,description\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "amount"):
                load_lines(path, "bank")


class SampleDataPipelineTest(unittest.TestCase):
    def test_all_injected_anomalies_are_detected(self):
        result = reconcile(load_lines(ROOT / "data/bank_statement.csv", "bank"),
                           load_lines(ROOT / "data/ledger.csv", "ledger"))
        self.assertEqual(result.count_by_kind(), {
            BreakKind.TIMING_DIFFERENCE: 2, BreakKind.AMOUNT_MISMATCH: 2, BreakKind.MISSING_IN_LEDGER: 1,
            BreakKind.BANK_CHARGE_NOT_BOOKED: 2, BreakKind.MISSING_IN_BANK: 2, BreakKind.POSSIBLE_DUPLICATE: 1})
        self.assertEqual(len(result.matched), 24)
        self.assertTrue(result.is_fully_explained)

    def test_committed_sample_data_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate_sample_data.main(Path(tmp, "data"))
            for name in ("bank_statement.csv", "ledger.csv"):
                self.assertTrue(filecmp.cmp(ROOT / "data" / name, Path(tmp, "data", name), shallow=False), name)

    def test_cli_writes_reports_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(["--bank", str(ROOT / "data/bank_statement.csv"),
                             "--ledger", str(ROOT / "data/ledger.csv"), "--out", tmp])
            self.assertEqual(code, 0)
            self.assertIn("Contrôle réussi", Path(tmp, "report.md").read_text(encoding="utf-8"))
            self.assertEqual(len(Path(tmp, "breaks.csv").read_text(encoding="utf-8-sig").splitlines()), 11)

    def test_cli_reports_a_clear_error_for_a_missing_file(self):
        self.assertEqual(cli.main(["--bank", "nope.csv", "--ledger", "nope.csv"]), 1)


if __name__ == "__main__":
    unittest.main()
