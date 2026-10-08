# Insurance Pricing Assurance & Investigation Workbench

A local application that validates renewal records, recalculates premiums using versioned rules, quantifies discrepancies and preserves investigation evidence. Python, Streamlit, SQLite and optional OpenAI Responses API.

## Run locally

Python 3.14 is tested. A virtual environment is already installed in this workspace.

```sh
.venv/bin/python -m streamlit run app.py
```

Open http://127.0.0.1:8501. The application binds to localhost. From a fresh checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m streamlit run app.py
```

To use AI, fill in `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`, then restart the application. Use a Responses-compatible model available to your account. The core demo and real-data reconciliation work without a key. No credentials are committed. The integration uses `store=False`; this does not by itself guarantee zero provider retention. Read the official [Responses API reference](https://developers.openai.com/api/reference/python/resources/responses/methods/create) for request behavior.

## First walkthrough

1. In Overview, create the 20,000-policy synthetic demo.
2. Review overcharges, undercharges, blocked records and segment exposure.
3. In Investigations, select a discrepancy and inspect its source record, rule and premium breakdown.
4. Record an analyst, status and investigation notes. Resolution or acceptance requires a rationale.
5. Export a filtered cohort or the full evidence bundle.

## Work with real data

**A document is evidence, not automatically a complete pricing specification.** This application supports the specific reviewed pricing contract in [docs/PRICING_CONTRACT.md](docs/PRICING_CONTRACT.md). Do not use the fictional rules to assess an actual insurer's premiums.

- **CSV / Excel:** Import a renewal portfolio in Import & reconcile. Choose a worksheet, map source columns, supply verified rating rules JSON, review the contract, and reconcile. Rows with missing fields, invalid values, unknown segments, dates without rules or duplicate policy IDs are blocked. Input dates must be ISO `YYYY-MM-DD`, amounts plain decimals, discounts fractions. Excel midnight date cells are normalised to ISO calendar dates; ambiguous text dates remain invalid rather than guessed.
- **PDF / DOCX / TXT / MD:** Read evidence in Evidence & documents, inspect extracted text and page references, then request OpenAI extraction. Exact quote citations are checked against the extracted source text. Review/edit every proposed record and approve it before importing. Supply independently reviewed rules JSON. Text PDFs are supported; scanned/image-only PDFs need OCR externally before importing. Tables in PDFs may extract imperfectly, so check the text preview.
- **Pricing manuals:** Attach as evidence and manually encode verified rates/effective dates in the rule JSON. The application does not turn arbitrary insurer formulas into executable code. Extend and test the engine if the real formula differs.

Source documents remain in memory until attached to a saved run. Saved runs retain extracted text, SHA-256 fingerprints, reviewed records and rules in SQLite. Original PDF/DOCX binaries are not retained; keep the originals securely outside the app. Uploaded evidence becomes part of the next saved run. Prior runs are immutable snapshots.

## AI behavior

AI is available for cited document extraction and investigation drafts. Every request has an explicit send action with disclosure of its context. Do not transmit documents you are not authorized to share. Document requests send selected readable text; explanation requests send the selected policy's mapped source fields, rules and retrieved evidence. API failures do not substitute fabricated responses. Explanation drafts are saved to the audit history; extraction drafts are reviewed in the UI. No AI output is used for premium arithmetic.

Extraction quotes validate provenance, not the correctness of every extracted field. Analyst review is mandatory. Evidence search is local keyword retrieval with page/section locators; it is not a semantic RAG service. A model can still produce an incorrect note, so check its citations and conclusions.

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
```

The evaluation uses 20,000 unique synthetic policies plus duplicates, separates injected labels from engine input, reports detection and blocked-record results, and writes `docs/evaluation.json`. Independent hand-calculated tests verify arithmetic and exposure directions. Synthetic defect tests measure the implemented scenarios, not real-world insurance performance. The generated sample portfolio is `examples/policies.csv`; corresponding labels remain separate in `examples/ground_truth.json`.

## Persistence and export

Default database: `data/workbench.sqlite3`. Set `ASSURANCE_DB` to change it. For backups, stop the app and copy the database. It contains policy data and extracted evidence in plain text; protect it with local filesystem permissions and disk encryption. No login, multi-user permissions, cloud deployment or automated remediation is provided.

Exports include reconciliation CSV, complete run JSON, versioned rules, evidence, audit history and a Markdown report. Text CSV cells are protected against spreadsheet formula injection. Treat full JSON exports as sensitive source data. Positive difference means recorded premium exceeds expected premium. Gross exposure sums absolute discrepant differences; net difference offsets overcharges and undercharges. Matched records within tolerance and blocked records are excluded from exposure. Closing a case leaves historical exposure unchanged.

## Docker (optional)

```sh
cp .env.example .env
docker compose up --build
```

Local persistent data mounts into `/app/data`; the port binds to `127.0.0.1`. Docker build is supplied but has not been validated unless BUILD_PROGRESS.md explicitly records it.

## Resume across usage limits

Read [BUILD_PROGRESS.md](BUILD_PROGRESS.md) for stage status and the next concrete task. It includes a ready-to-paste continuation prompt. No automation is required: your saved files and runs survive a model usage reset.

## Project layout

- `assurance/engine.py`: rule validation, Decimal arithmetic, reconciliation and KPIs.
- `assurance/storage.py`: SQLite runs, cases, audit and investigation exports.
- `assurance/documents.py`: local text extraction, fingerprints and evidence search.
- `assurance/ai.py`: isolated OpenAI Responses integration.
- `app.py`: local analyst workflow.
- `tests/`: calculation, persistence, export, document, mocked API and UI checks.
- `scripts/evaluate.py`: reproducible synthetic evaluation.
- `docs/`: contract, UAT, queries, handover and measured evaluation.
- `integrations/`: extension points for future policy administration APIs.
