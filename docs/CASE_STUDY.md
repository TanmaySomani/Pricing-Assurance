# Insurance Pricing Assurance & Investigation Workbench

## Problem and delivered workflow

A fictional motor insurer has released new rating tables and needs to investigate incorrect renewal premiums. The local workbench takes mapped portfolio files and reviewed document records, validates quality, selects effective rating versions, recalculates annual premiums, shows financial differences and saves investigation decisions with supporting evidence.

The analyst workflow is detect → explain → quantify → act. The analyst can inspect source fields and cent-level calculations, review hypotheses such as omitted discounts or stale rating tables, prioritise by absolute discrepancy, maintain case status and export a defensible investigation bundle. AI drafts notes and extracts cited policy records; Decimal arithmetic establishes the amounts.

## Measured synthetic results

On seed 42, 20,000 unique policies plus 200 duplicates produced 20,200 input rows. The engine identified all 2,455 injected pricing defects, with zero false positives or missed defects in the defined scenarios. It blocked all 592 unique policies with quality defects, accounting for 792 blocked input rows. Recorded gross simulated exposure was AUD 251,730.70. The initial local reconciliation benchmark took 0.215 seconds, excluding generation, UI, persistence and exports; timing varies by hardware. Detailed measurements are in evaluation.json.

These results demonstrate the implemented evaluation method on synthetic scenarios. The generator and engine share a pricing function, so independent hand-calculated tests separately verify arithmetic and rounding. No claim is made about real-world defect detection, analyst time savings or machine learning performance.

## Engineering and business evidence

Python, Streamlit, SQLite, versioned JSON rules, file fingerprints, preserved run inputs, case audit history, exported reports and isolated OpenAI Responses integration. Automated checks cover independent arithmetic, date boundaries, missing/invalid records, duplicates, persistence, exports, document parsing, citation validation and UI navigation. The UAT pack documents real-data verification requirements.

## Scope and next validation

The app supports one explicit annual AUD motor premium formula. A real insurer's contract must be reviewed and implemented accurately before its figures can support an investigation. Live OpenAI calls and real-document UAT await user credentials and representative inputs. Scanned PDFs require OCR before import. The app is local and single-user; no automatic customer decisions or refunds are made.

Screenshots are saved in docs/screenshots. Run README.md's demo walkthrough to present the project.
