import copy
import json
from decimal import Decimal
from pathlib import Path
import pytest
from assurance.engine import money, reconcile, summary, validate_rules

@pytest.fixture
def rules():
    return json.loads(Path('examples/rules.json').read_text())

@pytest.fixture
def row():
    return {'policy_id':'P-1','renewal_date':'2026-01-01','segment':'Metro','risk_factor':'1',
            'discount_rate':'0.10','recorded_premium':'1017.50','applied_rule_version':'MOTOR-2026'}

def test_independent_hand_calculation(rules,row):
    r = reconcile([row],rules)[0]
    # 1000 * 1 * .9 = 900; +25=925; tax=92.50; total=1017.50
    assert r['status'] == 'matched'
    assert r['expected'] == '1017.50'
    assert r['breakdown']['tax'] == '92.50'

def test_half_up():
    assert money('1.005') == Decimal('1.01')
    assert money('2.675') == Decimal('2.68')

@pytest.mark.parametrize('field,value', [('risk_factor','NaN'),('risk_factor','Infinity'),('risk_factor','0'),
    ('discount_rate','10'),('recorded_premium','-1'),('recorded_premium','10.001'),
    ('renewal_date','2026-02-30'),('renewal_date','2027-01-01'),('segment','Unknown'),('policy_id','')])
def test_invalid_data_blocked(rules,row,field,value):
    row[field] = value
    r = reconcile([row],rules)[0]
    assert r['status'] == 'blocked'
    assert r['difference'] is None
    assert r['issues']

def test_all_duplicate_occurrences_excluded(rules,row):
    results = reconcile([row,dict(row)],rules)
    assert summary(results)['blocked'] == 2
    assert summary(results)['gross_exposure'] == '0.00'

def test_rule_boundaries(rules,row):
    row.update(renewal_date='2025-12-31', recorded_premium='918.50')
    assert reconcile([row],rules)[0]['rule_version'] == 'MOTOR-2025'
    row.update(renewal_date='2026-01-01')
    assert reconcile([row],rules)[0]['rule_version'] == 'MOTOR-2026'

def test_overlap_rejected(rules):
    rules['versions'][0]['effective_to'] = '2026-01-01'
    with pytest.raises(ValueError,match='overlap'):
        validate_rules(rules)

def test_tolerance_and_direction(rules,row):
    row['recorded_premium'] = '1017.51'
    assert reconcile([row],rules)[0]['status'] == 'matched'
    row['recorded_premium'] = '1117.50'
    over = reconcile([row],rules)
    other = dict(row,policy_id='P-2',recorded_premium='967.50')
    total = summary(over + reconcile([other],rules))
    assert total['overcharges'] == '100.00'
    assert total['undercharges'] == '50.00'
    assert total['gross_exposure'] == '150.00'
    assert total['net_difference'] == '50.00'

def test_counterfactual_labels(rules,row):
    row['recorded_premium'] = '1127.50'
    assert 'Discount omitted' in reconcile([row],rules)[0]['hypotheses'][0]
    row.update(recorded_premium='918.50',applied_rule_version='MOTOR-2025')
    assert any('Expired rating' in h for h in reconcile([row],rules)[0]['hypotheses'])

def test_no_input_mutation(rules,row):
    original = copy.deepcopy(row)
    reconcile([row],rules)
    assert row == original
