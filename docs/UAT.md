# Acceptance and handover

| Analyst story | Acceptance criterion | Verification |
|---|---|---|
| Recalculate a known premium | Base 1000, risk 1, discount .10, fee 25, tax .10 returns 1017.50 | Independent hand calculation test |
| Detect financial differences | Recorded 1117.50 flags +100; 967.50 flags -50; gross 150 | Direction and totals test |
| Prevent unreliable impact | Missing/invalid fields and all duplicate occurrences are blocked and excluded | Validation tests |
| Select correct version | 2025-12-31 and 2026-01-01 select adjacent correct versions | Boundary test |
| Explain a plausible defect | Omitted discount and stale version produce labelled hypotheses | Counterfactual tests |
| Track a case | Status/notes persist after reopening; rationale required for closure | Persistence test |
| Export defensible evidence | Bundle includes source inputs, rules/hash, results and audit | ZIP content test |
| Review real document import | Verified exact quotes and mandatory analyst review precede import | Mocked extraction tests plus real-data UAT pending |
| Keep AI controlled | No arithmetic delegated; no silent fallback; store=False | Adapter tests |
| Navigate a working demo | Demo generation and all five screens render | Streamlit AppTest |

## Manual real-data UAT (requires user's data)

1. Supply an anonymised known-good portfolio and authoritative rules. Document unsupported formula terms before extending the engine.
2. For ten representative policies, calculate expected amounts independently, including effective-date boundaries, rounding, zero discount and missing data.
3. Compare a DOCX/text-PDF notice with extracted source text and reviewed records. A scanned page must produce a blocked extraction warning rather than guessed fields.
4. Confirm column mapping and numeric/date normalisation from the actual spreadsheet.
5. Reconcile against authoritative insurer totals. Investigate every difference and confirm exposure denominator.
6. Configure OpenAI credentials/model, explicitly send one permitted document/case, verify citations and account behavior. No live API validation is claimed before this step.
7. Save a resolved case, restart the app, confirm it persists and inspect the exported audit.

## Operating the app

Start with `.venv/bin/python -m streamlit run app.py`; stop with Ctrl-C. Restart after changing .env. Back up SQLite while the app is stopped. Keep original evidence documents alongside the database backup; only extracted text and fingerprints are saved in runs. Data is local plain text. Database snapshots are immutable in the UI; case notes and audit history remain editable/append-only through the workflow, not cryptographically tamper-proof.

No measured time-saving claim is made. A manual baseline and actual analyst task timing are future evaluation work. No machine learning ranking performance is claimed; priority uses absolute discrepancy as a transparent baseline.
