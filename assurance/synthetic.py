import random
from decimal import Decimal
from .engine import price


def generate(rules, count=20000, seed=42):
    rng = random.Random(seed)
    rows, truth = [], []
    rule, old = rules['versions'][-1], rules['versions'][0]
    for i in range(count):
        row = {'policy_id': f'DEMO-{i:06d}', 'renewal_date': '2026-06-15',
               'segment': rng.choice(list(rule['base_rates'])),
               'risk_factor': str(Decimal(rng.randint(80, 180)) / 100),
               'discount_rate': str(rng.choice([Decimal('.05'), Decimal('.10'), Decimal('.15')])),
               'applied_rule_version': rule['version']}
        expected, _ = price(rule, row)
        defect = 'clean'
        draw = rng.random()
        if draw < .04:
            expected, _ = price(rule, row, '0')
            defect = 'discount_omitted'
        elif draw < .08:
            expected, _ = price(rule, row, 1 - (1 - Decimal(row['discount_rate'])) ** 2)
            defect = 'discount_twice'
        elif draw < .12:
            expected, _ = price(old, row)
            row['applied_rule_version'] = old['version']
            defect = 'expired_rating'
        elif draw < .14:
            row['risk_factor'] = ''
            defect = 'missing_risk'
        row['recorded_premium'] = str(expected)
        rows.append(row)
        truth.append({'policy_id': row['policy_id'], 'defect': defect})
    # Deliberately duplicate otherwise clean policies. Truth is separate from input.
    for row in [r for r, t in zip(rows, truth) if t['defect'] == 'clean'][:max(1, count // 100)]:
        rows.append(dict(row))
        for t in truth:
            if t['policy_id'] == row['policy_id']:
                t['defect'] = 'duplicate'
                break
    return rows, truth
