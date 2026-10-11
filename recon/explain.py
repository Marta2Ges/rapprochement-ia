"""Explanations for each break.

Two layers:
1. Rules (always available, free, predictable) - write the explanation from templates.
2. Optional LLM (--llm) - rewrites the explanation more naturally.
   The LLM NEVER changes the break type, the amounts or the priority: it only receives
   breaks that the deterministic matcher has already found, and any failure falls back to rules.
"""
from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal

from .models import Break, BreakKind, Explanation

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("RECON_LLM_MODEL", "claude-sonnet-5-5")

KIND_LABELS_FR = {
    BreakKind.TIMING_DIFFERENCE: "Décalage de date",
    BreakKind.AMOUNT_MISMATCH: "Écart de montant",
    BreakKind.MISSING_IN_LEDGER: "Absent de la comptabilité",
    BreakKind.MISSING_IN_BANK: "Absent du relevé bancaire",
    BreakKind.BANK_CHARGE_NOT_BOOKED: "Frais bancaires non comptabilisés",
    BreakKind.POSSIBLE_DUPLICATE: "Doublon possible",
}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
PRIORITY_LABELS_FR = {"high": "Haute", "medium": "Moyenne", "low": "Basse"}


def fmt_chf(amount: Decimal) -> str:
    """Swiss formatting: -1250 -> 'CHF -1'250.00'."""
    sign = "-" if amount < 0 else ""
    whole, cents = f"{abs(amount):.2f}".split(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return f"CHF {sign}{chr(39).join(groups)}.{cents}"


def priority_for(brk: Break) -> str:
    """Simple, explicit and explainable: based on the amount at stake."""
    if brk.kind is BreakKind.TIMING_DIFFERENCE:
        return "low"
    if brk.kind is BreakKind.MISSING_IN_BANK and brk.detail.get("near_period_end"):
        return "low"  # cut-off: normal payment in transit at period end
    amount = abs(brk.impact)
    level = "high" if amount >= 1000 else "medium" if amount >= 100 else "low"
    if brk.kind in (BreakKind.POSSIBLE_DUPLICATE, BreakKind.AMOUNT_MISMATCH) and level == "low":
        level = "medium"  # a duplicate or an amount error is never trivial
    return level


# ----------------------------------------------------------------------------- rules
def explain_rules(brk: Break) -> Explanation:
    bank, ledger = brk.bank, brk.ledger
    priority = priority_for(brk)

    if brk.kind is BreakKind.TIMING_DIFFERENCE:
        text = (
            f"Même montant ({fmt_chf(bank.amount)}) des deux côtés, mais {brk.detail['days']} jours "
            f"séparent la date comptable ({ledger.date:%d.%m.%Y}) de la date bancaire ({bank.date:%d.%m.%Y})."
        )
        action = (
            "Aucune correction si ce délai est normal (délai de paiement). "
            "Vérifier la date de comptabilisation si le cas se répète."
        )
    elif brk.kind is BreakKind.AMOUNT_MISMATCH:
        text = (
            f"Écart de {fmt_chf(brk.detail['difference'])} sur la référence {bank.reference} : "
            f"banque {fmt_chf(bank.amount)} contre comptabilité {fmt_chf(ledger.amount)}."
        )
        if brk.detail.get("transposition"):
            text += " Les chiffres sont identiques dans un ordre différent : possible inversion de chiffres à la saisie."
        action = (
            "Vérifier la pièce d'origine. Si le montant bancaire est correct, passer une écriture "
            "de correction (escompte, frais ou erreur de saisie)."
        )
    elif brk.kind is BreakKind.MISSING_IN_LEDGER:
        text = (
            f"Opération bancaire de {fmt_chf(bank.amount)} (« {bank.description} », {bank.date:%d.%m.%Y}) "
            "sans écriture correspondante en comptabilité."
        )
        action = "Retrouver la pièce justificative, identifier l'opération, puis la comptabiliser."
    elif brk.kind is BreakKind.BANK_CHARGE_NOT_BOOKED:
        text = (
            f"Frais ou intérêts bancaires de {fmt_chf(bank.amount)} (« {bank.description} », "
            f"{bank.date:%d.%m.%Y}) non encore comptabilisés."
        )
        action = "Comptabiliser en charges bancaires."
    elif brk.kind is BreakKind.MISSING_IN_BANK:
        text = (
            f"Écriture comptable de {fmt_chf(ledger.amount)} (« {ledger.description} », "
            f"{ledger.date:%d.%m.%Y}) absente du relevé bancaire."
        )
        if brk.detail.get("near_period_end"):
            text += " Elle est datée de la fin de période : cas typique d'un paiement en transit."
            action = "Vérifier qu'elle figure sur le prochain relevé."
        else:
            text += " Elle n'est pas datée de la fin de période : l'absence est inhabituelle."
            action = "Contrôler que l'ordre de paiement a bien été exécuté par la banque."
    else:  # POSSIBLE_DUPLICATE
        text = (
            f"Le débit de {fmt_chf(abs(bank.amount))} (« {bank.description} ») apparaît deux fois "
            f"à la même date ({bank.date:%d.%m.%Y}) sur le relevé."
        )
        action = "Vérifier l'ordre de paiement puis demander à la banque l'annulation ou le remboursement du doublon."
    return Explanation(text=text, action=action, priority=priority, source="rules")


# ----------------------------------------------------------------------------- LLM layer
SYSTEM_PROMPT = (
    "Tu es un assistant comptable. Tu reçois une liste d'écarts de rapprochement bancaire "
    "DÉJÀ détectés par un programme. Tu ne modifies ni les montants, ni les types d'écart, "
    "ni les dates. Pour chaque écart, écris en français une explication claire de 1 à 2 phrases "
    "et une action recommandée courte. N'invente aucune information absente des données. "
    "Réponds UNIQUEMENT par un objet JSON de la forme : "
    '{"explanations": [{"id": "B001", "explanation": "...", "action": "..."}]}'
)


def _break_payload(brk: Break) -> dict:
    line = brk.bank or brk.ledger
    return {
        "id": brk.id,
        "type": brk.kind.value,
        "date_banque": brk.bank.date.isoformat() if brk.bank else None,
        "date_comptabilite": brk.ledger.date.isoformat() if brk.ledger else None,
        "description": line.description,
        "reference": line.reference,
        "montant_banque": str(brk.bank.amount) if brk.bank else None,
        "montant_comptabilite": str(brk.ledger.amount) if brk.ledger else None,
        "impact": str(brk.impact),
        "details": {k: str(v) for k, v in brk.detail.items()},
    }


def _extract_json(text: str) -> dict:
    """Tolerate code fences or a sentence around the JSON object."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the model answer")
    return json.loads(text[start : end + 1])


def explain_with_llm(breaks: list[Break], client, model: str = DEFAULT_MODEL) -> dict[str, tuple[str, str]]:
    """Ask the model to rewrite explanations. `client` is an anthropic.Anthropic-like object."""
    payload = json.dumps([_break_payload(b) for b in breaks], ensure_ascii=False)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )
    answer = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    items = _extract_json(answer)["explanations"]
    known_ids = {b.id for b in breaks}
    result = {}
    for item in items:
        if item.get("id") in known_ids and item.get("explanation") and item.get("action"):
            result[item["id"]] = (item["explanation"].strip(), item["action"].strip())
    return result


def explain_all(breaks: list[Break], client=None, model: str = DEFAULT_MODEL) -> dict[str, Explanation]:
    """Rules for everything; the LLM (if given) only improves the wording."""
    explanations = {b.id: explain_rules(b) for b in breaks}
    if client is None or not breaks:
        return explanations
    try:
        rewritten = explain_with_llm(breaks, client, model)
    except Exception as exc:  # network, API or parsing error: keep the rules-based text
        logger.warning("LLM explanations unavailable (%s); using rule-based text.", exc)
        return explanations
    for break_id, (text, action) in rewritten.items():
        base = explanations[break_id]
        explanations[break_id] = Explanation(text=text, action=action, priority=base.priority, source="llm")
    return explanations
