"""Separate ground truth evaluation; labels are never supplied to the engine."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assurance.engine import reconcile, summary
from assurance.synthetic import generate
from assurance.storage import csv_bytes

root = Path(__file__).resolve().parents[1]
rules = json.loads((root/'examples/rules.json').read_text())
rows,truth = generate(rules,20000)
start = time.perf_counter()
results = reconcile(rows,rules)
elapsed = time.perf_counter()-start
labels = {t['policy_id']:t['defect'] for t in truth}
pricing_defects = {'discount_omitted','discount_twice','expired_rating'}
expected = {p for p,d in labels.items() if d in pricing_defects}
detected = {r['policy_id'] for r in results if r['status'] == 'discrepancy'}
blocked_expected = {p for p,d in labels.items() if d in {'duplicate','missing_risk'}}
blocked_found = {r['policy_id'] for r in results if r['status'] == 'blocked'}
report = {'dataset':'Synthetic motor renewals, seed 42; not real-world validation',
          'unique_policies':len(truth),'input_rows':len(rows),'seconds':round(elapsed,3),
          'pricing_true_positives':len(expected & detected),'pricing_false_positives':len(detected-expected),
          'pricing_false_negatives':len(expected-detected),'blocked_expected':len(blocked_expected),
          'blocked_detected':len(blocked_found),'blocked_missed':len(blocked_expected-blocked_found),
          'summary':summary(results)}
(root/'docs/evaluation.json').write_text(json.dumps(report,indent=2))
(root/'examples/policies.csv').write_bytes(csv_bytes(rows[:100]))
(root/'examples/ground_truth.json').write_text(json.dumps(truth[:100],indent=2))
print(json.dumps(report,indent=2))
assert not report['pricing_false_positives'] and not report['pricing_false_negatives']
assert not report['blocked_missed']
