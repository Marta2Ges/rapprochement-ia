import json
import unittest
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

from recon.explain import explain_all, explain_rules, fmt_chf, priority_for
from recon.matcher import reconcile
from recon.models import Break, BreakKind, Line

D1 = date(2026, 9, 10)


def sample_breaks():
    bank = [Line("bank", 2, D1, "VIR EMIS X", D("-2400.00"), "R1"),
            Line("bank", 3, D1, "FRAIS DE TENUE DE COMPTE", D("-45.00"))]
    ledger = [Line("ledger", 2, D1, "Paiement X", D("-2040.00"), "R1")]
    return reconcile(bank, ledger).breaks


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create without any network call."""

    def __init__(self, answer=None, error=None):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._answer, self._error = answer, error

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._answer)])


class FormattingTest(unittest.TestCase):
    def test_swiss_amount_format(self):
        self.assertEqual(fmt_chf(D("1250")), "CHF 1'250.00")
        self.assertEqual(fmt_chf(D("-1234567.5")), "CHF -1'234'567.50")
        self.assertEqual(fmt_chf(D("0")), "CHF 0.00")


class RulesTest(unittest.TestCase):
    def test_amount_mismatch_mentions_transposition_in_french(self):
        brk = next(b for b in sample_breaks() if b.kind is BreakKind.AMOUNT_MISMATCH)
        explanation = explain_rules(brk)
        self.assertIn("inversion de chiffres", explanation.text)
        self.assertIn("CHF -2'400.00", explanation.text)
        self.assertEqual(explanation.source, "rules")

    def test_priority_depends_on_amount_and_kind(self):
        line = Line("bank", 2, D1, "X", D("1"))
        make = lambda kind, impact, **detail: Break("B001", kind, line, line, D(impact), detail)
        self.assertEqual(priority_for(make(BreakKind.MISSING_IN_LEDGER, "1500")), "high")
        self.assertEqual(priority_for(make(BreakKind.MISSING_IN_LEDGER, "150")), "medium")
        self.assertEqual(priority_for(make(BreakKind.MISSING_IN_LEDGER, "15")), "low")
        self.assertEqual(priority_for(make(BreakKind.AMOUNT_MISMATCH, "15")), "medium")
        self.assertEqual(priority_for(make(BreakKind.TIMING_DIFFERENCE, "0")), "low")
        self.assertEqual(priority_for(make(BreakKind.MISSING_IN_BANK, "5000", near_period_end=True)), "low")


class LlmLayerTest(unittest.TestCase):
    def test_llm_rewrites_text_but_keeps_priority_and_amounts(self):
        breaks = sample_breaks()
        answer = json.dumps({"explanations": [
            {"id": breaks[0].id, "explanation": "Texte LLM", "action": "Action LLM"}]})
        client = FakeClient(answer="```json\n" + answer + "\n```")  # code fence must be tolerated
        result = explain_all(breaks, client=client, model="test-model")
        self.assertEqual(result[breaks[0].id].text, "Texte LLM")
        self.assertEqual(result[breaks[0].id].source, "llm")
        self.assertEqual(result[breaks[0].id].priority, explain_rules(breaks[0]).priority)
        self.assertEqual(result[breaks[1].id].source, "rules")  # not returned by the LLM
        self.assertEqual(client.calls[0]["model"], "test-model")

    def test_unknown_ids_are_ignored(self):
        answer = json.dumps({"explanations": [{"id": "B999", "explanation": "x", "action": "y"}]})
        result = explain_all(sample_breaks(), client=FakeClient(answer=answer))
        self.assertTrue(all(e.source == "rules" for e in result.values()))

    def test_invalid_json_falls_back_to_rules(self):
        result = explain_all(sample_breaks(), client=FakeClient(answer="désolé, pas de JSON"))
        self.assertTrue(all(e.source == "rules" for e in result.values()))

    def test_api_error_falls_back_to_rules(self):
        with self.assertLogs("recon.explain", level="WARNING"):
            result = explain_all(sample_breaks(), client=FakeClient(error=RuntimeError("network down")))
        self.assertTrue(all(e.source == "rules" for e in result.values()))

    def test_payload_sent_to_the_model_contains_no_free_text_beyond_the_break_data(self):
        client = FakeClient(answer=json.dumps({"explanations": []}))
        explain_all(sample_breaks(), client=client)
        sent = json.loads(client.calls[0]["messages"][0]["content"])
        self.assertEqual({"id", "type", "date_banque", "date_comptabilite", "description", "reference",
                          "montant_banque", "montant_comptabilite", "impact", "details"}, set(sent[0]))


if __name__ == "__main__":
    unittest.main()
