# Rapport de rapprochement bancaire

| Total relevé bancaire | Total comptabilité | Différence à expliquer |
|---:|---:|---:|
| CHF 2'952.10 | CHF 1'698.05 | CHF 1'254.05 |

✅ **Contrôle réussi** : les 10 écarts ci-dessous expliquent exactement la différence (CHF 1'254.05).

24 opérations rapprochées automatiquement.

## Synthèse par type d'écart

| Type | Nombre | Impact sur la différence |
|---|---:|---:|
| Écart de montant | 2 | CHF -410.00 |
| Frais bancaires non comptabilisés | 2 | CHF -68.50 |
| Absent du relevé bancaire | 2 | CHF 2'602.55 |
| Absent de la comptabilité | 1 | CHF 1'134.80 |
| Doublon possible | 1 | CHF -2'004.80 |
| Décalage de date | 2 | CHF 0.00 |

## Détail des écarts (triés par priorité)

| ID | Priorité | Type | Date | Impact sur la différence | Explication | Action recommandée |
|---|---|---|---|---:|---|---|
| B002 | Haute | Doublon possible | 13.09.2026 | CHF -2'004.80 | Le débit de CHF 2'004.80 (« VIR EMIS LOGISTIQUE LAC LÉMAN ») apparaît deux fois à la même date (13.09.2026) sur le relevé. | Vérifier l'ordre de paiement puis demander à la banque l'annulation ou le remboursement du doublon. |
| B004 | Haute | Absent de la comptabilité | 18.09.2026 | CHF 1'134.80 | Opération bancaire de CHF 1'134.80 (« VIR RECU REMBOURSEMENT TVA », 18.09.2026) sans écriture correspondante en comptabilité. | Retrouver la pièce justificative, identifier l'opération, puis la comptabiliser. |
| B001 | Moyenne | Écart de montant | 05.09.2026 | CHF -360.00 | Écart de CHF -360.00 sur la référence FA-1008 : banque CHF -2'400.00 contre comptabilité CHF -2'040.00. Les chiffres sont identiques dans un ordre différent : possible inversion de chiffres à la saisie. | Vérifier la pièce d'origine. Si le montant bancaire est correct, passer une écriture de correction (escompte, frais ou erreur de saisie). |
| B005 | Moyenne | Écart de montant | 23.09.2026 | CHF -50.00 | Écart de CHF -50.00 sur la référence FC-2003 : banque CHF 2'195.25 contre comptabilité CHF 2'245.25. | Vérifier la pièce d'origine. Si le montant bancaire est correct, passer une écriture de correction (escompte, frais ou erreur de saisie). |
| B007 | Basse | Absent du relevé bancaire | 29.09.2026 | CHF 1'860.40 | Écriture comptable de CHF -1'860.40 (« Paiement fournisseur Transports Jura », 29.09.2026) absente du relevé bancaire. Elle est datée de la fin de période : cas typique d'un paiement en transit. | Vérifier qu'elle figure sur le prochain relevé. |
| B010 | Basse | Absent du relevé bancaire | 30.09.2026 | CHF 742.15 | Écriture comptable de CHF -742.15 (« Paiement fournisseur Logistique Lac Léman », 30.09.2026) absente du relevé bancaire. Elle est datée de la fin de période : cas typique d'un paiement en transit. | Vérifier qu'elle figure sur le prochain relevé. |
| B009 | Basse | Frais bancaires non comptabilisés | 30.09.2026 | CHF -45.00 | Frais ou intérêts bancaires de CHF -45.00 (« FRAIS DE TENUE DE COMPTE », 30.09.2026) non encore comptabilisés. | Comptabiliser en charges bancaires. |
| B008 | Basse | Frais bancaires non comptabilisés | 30.09.2026 | CHF -23.50 | Frais ou intérêts bancaires de CHF -23.50 (« COMMISSION VIREMENTS INTERNATIONAUX », 30.09.2026) non encore comptabilisés. | Comptabiliser en charges bancaires. |
| B003 | Basse | Décalage de date | 14.09.2026 | CHF 0.00 | Même montant (CHF -1'768.30) des deux côtés, mais 9 jours séparent la date comptable (05.09.2026) de la date bancaire (14.09.2026). | Aucune correction si ce délai est normal (délai de paiement). Vérifier la date de comptabilisation si le cas se répète. |
| B006 | Basse | Décalage de date | 24.09.2026 | CHF 0.00 | Même montant (CHF 7'608.55) des deux côtés, mais 14 jours séparent la date comptable (10.09.2026) de la date bancaire (24.09.2026). | Aucune correction si ce délai est normal (délai de paiement). Vérifier la date de comptabilisation si le cas se répète. |
