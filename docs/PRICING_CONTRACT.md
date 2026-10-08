# Business and pricing contract — v1

## Scope

One annual motor renewal premium per policy, AUD, one approved rating contract per run. The workbench answers which premiums differ, by how much, which data prevent reliable calculation and what evidence supports investigation. The fictional insurer is demonstration data only.

Current process: analyst receives a portfolio, manually identifies rating versions, recalculates premiums, investigates differences and writes an impact report. Future process: import → review schema and evidence → deterministic reconciliation → prioritise discrepancies/blocked rows → inspect source/rule/breakdown → save investigation → export evidence.

## Canonical policy schema

| Field | Required | Contract |
|---|---|---|
| policy_id | Yes | Nonempty unique identifier within run; all duplicate occurrences blocked |
| renewal_date | Yes | ISO YYYY-MM-DD; selects one inclusive effective rule period |
| segment | Yes | Exact matching base_rates key in applicable version |
| risk_factor | Yes | Decimal, greater than zero and at most 100; verified rating input |
| discount_rate | Yes | Decimal fraction in [0,1]; 0.10 means 10% |
| recorded_premium | Yes | Nonnegative annual AUD amount with at most two decimal places |
| applied_rule_version | No | Source-record version used to investigate stale rating tables |

Additional document extraction fields record source_document, source_locator and evidence_quote. Unknown fields must remain blank; do not infer them from a premium. The app's row locator counts canonical imported rows starting at 2 after a header; after worksheet selection or document review it is a canonical row locator, not a claim about the original page/worksheet line.

## Pricing rules JSON

Top-level currency must be AUD. versions is a nonempty list. Each version has a unique version identifier, inclusive effective_from/effective_to dates, positive segment base_rates, nonnegative fee, tax_rate fraction in [0,1], and a nonempty source evidence reference. Overlapping effective periods are rejected. Gaps are allowed but policies in gaps are blocked. `examples/rules.json` provides the schema, with fictional rates.

Formula order (every round is Decimal ROUND_HALF_UP to cents):

1. rated = round(base_rates[segment] × risk_factor)
2. discounted = round(rated × (1 − discount_rate))
3. fee = round(fee)
4. tax = round((discounted + fee) × tax_rate)
5. expected = discounted + fee + tax
6. difference = recorded − expected

Tax applies to discounted premium plus fee in this fictional contract. The default discrepancy tolerance is AUD 0.01, inclusive: only abs(difference) > tolerance is flagged. Floating-point values in charts are for display; calculation and aggregate exposure use Decimal. Number inputs must be finite and absolute values at most 1 billion.

## Root cause and priority

Omitted discount, twice-applied discount and expired rating table are tested as counterfactual calculations. Matching the recorded amount provides an investigation hypothesis; it does not prove the underlying operational cause. Unexpected differences remain unexplained. Cases sort by absolute discrepancy; blocked records remain accessible but have no guessed financial impact. Applied-version differences appear as issues even if premiums match.

## KPI definitions

Discrepancy rate = discrepant calculable rows / all calculable rows. Affected policies = discrepant rows, unique because duplicates are blocked. Overcharge = sum of positive discrepant differences. Undercharge = absolute sum of negative discrepant differences. Gross exposure = overcharge + undercharge. Net difference = overcharge − undercharge. Blocked record count is rows, not unique policy IDs. This prevents duplicate financial exposure. Case resolution does not change the immutable run.

## Unsupported business rules

Multi-cover products, multiple renewals per policy per batch, discounts with caps or eligibility rules, prorating, instalment charges, separate levies, geographic tax differences, commission, min/max premiums, currency conversion and adjustment/refund calculations require an extension to the engine and independently reviewed tests. Configuration JSON supplies rates and dates; it does not implement arbitrary formulas. Real deployment requires comparison against authoritative insurer calculations and UAT on supplied documents.
