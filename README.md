# Rapprochement bancaire assisté par IA

[![Tests](https://github.com/Marta2Ges/rapprochement-ia/actions/workflows/tests.yml/badge.svg)](https://github.com/Marta2Ges/rapprochement-ia/actions/workflows/tests.yml)

Outil en ligne de commande (Python) qui compare un **relevé bancaire** et une **comptabilité**, rapproche automatiquement les opérations, classe chaque écart et l'explique en français.

> Projet d'apprentissage et de portfolio, inspiré de mon expérience des réconciliations bancaires (investigation des suspens dans GTMatch). **Toutes les données sont synthétiques** : les entreprises sont fictives.

*English summary at the bottom.*

## Pourquoi ce projet

Le rapprochement bancaire est une tâche répétitive où l'exactitude est non négociable… mais où comprendre *pourquoi* un écart existe prend du temps. J'ai voulu séparer clairement les deux problèmes :

| Besoin | Approche | Pourquoi |
|---|---|---|
| Décider si deux lignes correspondent | **Code déterministe** (règles + tests) | Exact, reproductible, auditable, gratuit |
| Expliquer un écart en langage naturel | **LLM optionnel** (`--llm`) | Là où le langage apporte de la valeur |

Le LLM ne voit que les écarts déjà détectés, ne peut modifier ni les montants ni les types d'écart, et toute erreur retombe automatiquement sur les explications par règles.

## Ce que fait l'outil

- Rapproche les opérations par **montant, date, référence et similarité du libellé**.
- Classe les écarts en 6 types : décalage de date, écart de montant (avec détection d'**inversion de chiffres**, ex. 2'040.00 saisi 2'400.00), opération absente de la comptabilité, opération absente du relevé (avec gestion de la **fin de période / cut-off**), frais bancaires non comptabilisés, doublon possible.
- Vérifie que **les écarts expliquent exactement la différence** entre le total du relevé et celui de la comptabilité (contrôle de cohérence, testé sur des données aléatoires).
- Produit un rapport Markdown trié par priorité et un CSV pour Excel.

### Exemple de résultat (`output/report.md`)

| Type | Nombre | Impact sur la différence |
|---|---:|---:|
| Écart de montant | 2 | CHF -410.00 |
| Frais bancaires non comptabilisés | 2 | CHF -68.50 |
| Absent du relevé bancaire | 2 | CHF 2'602.55 |
| Absent de la comptabilité | 1 | CHF 1'134.80 |
| Doublon possible | 1 | CHF -2'004.80 |
| Décalage de date | 2 | CHF 0.00 |

> ✅ Contrôle réussi : les 10 écarts expliquent exactement la différence (CHF 1'254.05).

## Utilisation

Aucune dépendance pour le cœur de l'outil (bibliothèque standard, Python 3.10+, testé avec 3.12).

```bash
python scripts/generate_sample_data.py          # (re)génère les données synthétiques
python -m recon --bank data/bank_statement.csv --ledger data/ledger.csv --out output
```

Formats acceptés : CSV avec les colonnes `date`, `description`, `amount` et, en option, `reference`. Dates `AAAA-MM-JJ` ou `JJ.MM.AAAA`, montants au format suisse (`1'250.50`) ou standard.

### Explications reformulées par un LLM (optionnel)

```bash
pip install -r requirements-llm.txt
export ANTHROPIC_API_KEY=...        # votre clé
export RECON_LLM_MODEL=...          # optionnel : le modèle par défaut peut devoir être adapté
python -m recon --bank data/bank_statement.csv --ledger data/ledger.csv --llm
```

Sans clé ou sans le paquet, l'outil le signale et utilise les explications par règles.

## Architecture

```
recon/
├── models.py     # structures de données (Line, Break, Explanation)
├── loader.py     # lecture des CSV, formats suisses, messages d'erreur avec numéro de ligne
├── matcher.py    # rapprochement déterministe (3 passes) + contrôle de cohérence
├── explain.py    # explications par règles + couche LLM optionnelle avec repli
├── report.py     # rapport Markdown et CSV
└── __main__.py   # ligne de commande
scripts/generate_sample_data.py   # données synthétiques reproductibles, anomalies injectées
tests/                            # 29 tests (unittest)
```

Le rapprochement se fait en trois passes successives, de la plus sûre à la moins sûre : correspondance exacte, décalage de date, écart de montant sur une même référence. Ce qui reste est classé (doublon, frais bancaires, opération inconnue ou en transit).

## Choix de conception et limites

- **Pourquoi pas « tout au LLM » ?** Un LLM peut se tromper sur un montant, coûte à chaque appel et n'est pas reproductible. Pour un contrôle comptable, la décision doit rester vérifiable.
- **Appariement glouton.** Simple, rapide et explicable, mais pas globalement optimal. Une alternative serait un algorithme d'affectation (méthode hongroise).
- **Un pour un uniquement.** Un virement groupé couvrant plusieurs factures n'est pas géré (correspondance 1-N).
- **Similarité du libellé avec `difflib`.** Suffisant ici, mais sans compréhension sémantique. Des embeddings pourraient améliorer les cas difficiles.
- **Priorité fixée par seuils de montant** (1'000 / 100 CHF). Dans la réalité, ces règles dépendent du client et de la matérialité.
- **Une seule devise, une seule période.**
- **Confidentialité.** Avec de vraies données, les libellés envoyés à une API externe devraient être anonymisés ou traités par un fournisseur offrant les garanties contractuelles nécessaires. **Ne jamais utiliser de données clients réelles dans ce dépôt.**

## Tests

```bash
python -m unittest -v
```

Les 29 tests couvrent chaque type d'écart, le parsing des formats suisses, la reproductibilité des données d'exemple et un test « de propriété » sur des données aléatoires : *quelle que soit l'entrée, chaque ligne est utilisée une seule fois et les écarts expliquent la différence*. La couche LLM est testée avec un client simulé (réponse valide, JSON entouré de balises, JSON invalide, identifiants inconnus, erreur réseau) ; un appel réel à l'API nécessite une clé.

## Pistes d'amélioration

- Correspondances 1-N (paiements groupés) et multi-devises.
- Import des formats bancaires standards (CAMT.053, MT940).
- Règles de priorité configurables (fichier YAML).
- Petite interface web pour charger les fichiers et filtrer les écarts.
- Évaluation de la qualité des explications LLM sur un jeu de cas annotés.

## Comment ce projet a été réalisé

Ce projet a été conçu et écrit avec l'aide d'un assistant IA (Claude, d'Anthropic) ; je l'ai relu, exécuté et testé, et je peux en expliquer la logique. Certaines modifications demandent encore de l'accompagnement : c'est aussi une manière d'apprendre et d'explorer le développement assisté par agents.

## Licence

MIT, voir [LICENSE](LICENSE).

---

## English summary

A zero-dependency Python CLI that reconciles a bank statement against a ledger, classifies every discrepancy (timing difference, amount mismatch with digit-transposition detection, missing on either side with period-end cut-off handling, unbooked bank charges, possible duplicates) and explains each one in French. Matching is **deterministic and tested**; an **optional LLM layer** (`--llm`) only rewrites the explanations of already-detected breaks and falls back to rules on any failure. A built-in check verifies that the breaks explain the bank-vs-ledger difference to the cent. All data is synthetic. Run `python -m unittest -v` for the 29 tests.
