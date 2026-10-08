import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FIELDS = ['policy_id', 'renewal_date', 'segment', 'risk_factor', 'discount_rate', 'recorded_premium', 'applied_rule_version']
CENT = Decimal('0.01')


def number(value):
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f'Invalid number: {value!r}') from None
    if not result.is_finite() or abs(result) > Decimal('1000000000'):
        raise ValueError('Number must be finite and within supported bounds')
    return result


def money(value):
    return number(value).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_rules(rules):
    if not isinstance(rules, dict) or rules.get('currency') != 'AUD':
        raise ValueError('Rules require currency AUD')
    if not isinstance(rules.get('versions'), list) or not rules['versions']:
        raise ValueError('At least one rule version is required')
    seen, periods = set(), []
    for rule in rules['versions']:
        version = rule['version']
        if not isinstance(version, str) or not version.strip() or version in seen:
            raise ValueError('Rule versions must be unique nonempty strings')
        seen.add(version)
        start, end = date.fromisoformat(rule['effective_from']), date.fromisoformat(rule['effective_to'])
        if end < start:
            raise ValueError('Rule end date precedes start date')
        if any(start <= old_end and end >= old_start for old_start, old_end in periods):
            raise ValueError('Rule effective periods overlap (end dates are inclusive)')
        periods.append((start, end))
        if not rule.get('base_rates') or not isinstance(rule['base_rates'], dict):
            raise ValueError('Base rates must be a nonempty segment mapping')
        for rate in rule['base_rates'].values():
            if number(rate) <= 0:
                raise ValueError('Base rates must be positive')
        if number(rule['fee']) < 0 or not 0 <= number(rule['tax_rate']) <= 1:
            raise ValueError('Invalid fee or tax rate')
        if not isinstance(rule.get('source'), str) or not rule['source'].strip():
            raise ValueError('Each version requires an evidence source')
    return rules


def rule_hash(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()


def price(rule, row, discount=None):
    base = number(rule['base_rates'][row['segment']])
    risk = number(row['risk_factor'])
    reduction = number(row['discount_rate'] if discount is None else discount)
    rated = money(base * risk)
    discounted = money(rated * (1 - reduction))
    fee = money(rule['fee'])
    tax = money((discounted + fee) * number(rule['tax_rate']))
    total = money(discounted + fee + tax)
    return total, {'base': str(base), 'risk_factor': str(risk), 'rated': str(rated),
                   'discount_rate': str(reduction), 'discounted': str(discounted),
                   'fee': str(fee), 'tax': str(tax), 'expected': str(total)}


def reconcile(rows, rules, tolerance='0.01'):
    validate_rules(rules)
    tolerance = number(tolerance)
    if tolerance < 0:
        raise ValueError('Tolerance cannot be negative')
    ids = Counter(str(r.get('policy_id', '')).strip() for r in rows)
    results = []
    versions = {v['version']: v for v in rules['versions']}
    for line, original in enumerate(rows, 2):
        row = {k: str(v).strip() if v is not None else '' for k, v in original.items()}
        out = {'source_row': line, 'policy_id': row.get('policy_id', ''), 'segment': row.get('segment', ''),
               'status': 'blocked', 'issues': [], 'source': original, 'expected': None, 'difference': None,
               'recorded': None, 'rule_version': None, 'breakdown': {}, 'hypotheses': []}
        required = FIELDS[:-1]
        missing = [f for f in required if not row.get(f)]
        if missing:
            out['issues'].append('Missing fields: ' + ', '.join(missing))
        if row.get('policy_id') and ids[row['policy_id']] > 1:
            out['issues'].append('Duplicate policy_id; all occurrences excluded from exposure')
        if out['issues']:
            results.append(out)
            continue
        try:
            when = date.fromisoformat(row['renewal_date'])
            active = [r for r in rules['versions'] if date.fromisoformat(r['effective_from']) <= when <= date.fromisoformat(r['effective_to'])]
            if len(active) != 1:
                raise ValueError('No applicable rating version for renewal date')
            rule = active[0]
            if row['segment'] not in rule['base_rates']:
                raise ValueError('Unknown segment in applicable rating version')
            if not 0 < number(row['risk_factor']) <= 100:
                raise ValueError('risk_factor must be greater than 0 and at most 100')
            if not 0 <= number(row['discount_rate']) <= 1:
                raise ValueError('discount_rate must be a fraction between 0 and 1')
            recorded = number(row['recorded_premium'])
            if recorded < 0 or recorded != money(recorded):
                raise ValueError('recorded_premium must be nonnegative with at most two decimal places')
            expected, breakdown = price(rule, row)
            difference = money(recorded - expected)
            out.update(recorded=str(recorded), expected=str(expected), difference=str(difference),
                       rule_version=rule['version'], breakdown=breakdown,
                       status='discrepancy' if abs(difference) > tolerance else 'matched')
            applied = row.get('applied_rule_version', '')
            if applied and applied != rule['version']:
                out['issues'].append(f'Applied version {applied} differs from applicable {rule["version"]}')
            if out['status'] == 'discrepancy':
                if number(row['discount_rate']) > 0:
                    omitted, _ = price(rule, row, '0')
                    twice, _ = price(rule, row, 1 - (1 - number(row['discount_rate'])) ** 2)
                    for value, label in [(omitted, 'Discount omitted'), (twice, 'Discount applied twice')]:
                        if abs(value - recorded) <= tolerance:
                            out['hypotheses'].append(label + ' (counterfactual match; confirm source evidence)')
                if applied in versions and applied != rule['version'] and row['segment'] in versions[applied]['base_rates']:
                    old, _ = price(versions[applied], row)
                    if abs(old - recorded) <= tolerance:
                        out['hypotheses'].append('Expired rating table (recorded version and counterfactual match)')
                if not out['hypotheses']:
                    out['hypotheses'].append('Unexplained discrepancy; investigate source data and rule assumptions')
        except (ValueError, KeyError, InvalidOperation) as exc:
            out['issues'].append(str(exc))
        results.append(out)
    return results


def summary(results):
    valid = [r for r in results if r['status'] != 'blocked']
    flagged = [r for r in valid if r['status'] == 'discrepancy']
    over = sum((number(r['difference']) for r in flagged if number(r['difference']) > 0), Decimal(0))
    under = -sum((number(r['difference']) for r in flagged if number(r['difference']) < 0), Decimal(0))
    return {'rows': len(results), 'calculable': len(valid), 'blocked': len(results) - len(valid),
            'affected': len(flagged), 'discrepancy_rate': len(flagged) / len(valid) if valid else 0,
            'overcharges': str(money(over)), 'undercharges': str(money(under)),
            'gross_exposure': str(money(over + under)), 'net_difference': str(money(over - under))}
