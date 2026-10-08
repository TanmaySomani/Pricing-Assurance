# Build checkpoints

Read this file first when resuming work. Each stage has runnable acceptance checks.

| Stage | Deliverable | Status |
|---|---|---|
| 1 | Business contract, schema, versioned rules, Decimal pricing and synthetic data | Complete |
| 2 | File validation, reconciliation, SQLite runs/cases/audit, exports | Complete |
| 3 | Local dashboard, ingestion mapping, investigations and evidence | Complete |
| 4 | OpenAI explanations and reviewed document extraction | Implemented and mocked tests passed; live API check pending credentials |
| 5 | Acceptance tests, measured evaluation, Docker and handover | Local checks passed; Docker validation pending Docker installation |

## Resume instruction

“Continue this project from BUILD_PROGRESS.md. Read README.md and docs/PRICING_CONTRACT.md, inspect existing implementation and tests, then finish the first incomplete stage. Update checkpoints with actual evidence. Never replace validated insurer rules with synthetic examples.”

## Boundaries

Local single-user application. Synthetic demonstration is separate from real runs. Real premiums require verified versioned rating rules; documents alone may not contain enough information. AI extraction is a draft that needs human review. Premium arithmetic remains deterministic. API credentials belong in .env, never source code.

## Verification checkpoint — 8 October 2026

- Final test run: 26 passed in 3.37 seconds. Covers all five UI pages, real Excel date cells and leading-zero policy identifiers, calculation and evidence workflows.
- Synthetic evaluation: 20,000 unique policies / 20,200 rows; 2,455 pricing defects detected; zero false positives or missed pricing defects; all 592 unique policies with data defects blocked (792 rows). Initial measured reconciliation: 0.215 seconds, excluding generation and UI. See docs/evaluation.json.
- Local server started on http://127.0.0.1:8501. Browser verified the dashboard; demo run is saved in data/workbench.sqlite3.
- Browser upload verification: examples/policies.csv and examples/rules.json imported, mapped, reviewed and saved as a synthetic run. 100 rows reconciled, 12 discrepancies; overview verified the saved cohort.
- Dependency versions locked in requirements.txt; .venv installed.
- OpenAI request shape, JSON handling, exact citation validation and store=False tested using a mock client. No live API call made: no credentials/model supplied.
- Dockerfile and compose.yaml supplied. Docker executable is unavailable here; build not tested.

## Next tasks when inputs are available

1. Set OPENAI_API_KEY and OPENAI_MODEL in .env; restart. Run one extraction using examples/renewal_notice.txt, review fields and quotes, reconcile with examples/rules.json, then request an explanation. Verify provider errors and citations with the actual account.
2. User supplies a representative real policy notice, portfolio and authoritative rating contract. Complete docs/UAT.md; extend formula and tests for every unsupported term. Do not claim generic real-document correctness before this comparison.
3. If real inputs are scanned, implement and validate local OCR (currently the app blocks image-only pages and explains how to proceed).
4. When Docker is installed, run docker compose up --build, verify persisted cases after restart and record the result here.

## Optional portfolio extensions

Record a 90-second walkthrough; add held-out scenario evaluation and compare anomaly ranking against the implemented discrepancy baseline; measure analyst tasks against a manual baseline before claiming time savings. These are not prerequisites for the delivered local reconciliation workflow.
