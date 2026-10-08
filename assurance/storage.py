import csv
import io
import json
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .engine import rule_hash, summary


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path='data/workbench.sqlite3'):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created TEXT, label TEXT, mode TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS cases(run_id TEXT, source_row INTEGER, status TEXT, owner TEXT, notes TEXT,
              PRIMARY KEY(run_id,source_row));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, created TEXT, run_id TEXT, source_row INTEGER, action TEXT, payload TEXT);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def save_run(self, label, mode, rows, rules, results, documents=None, tolerance='0.01'):
        run_id = str(uuid.uuid4())
        payload = {'rows': rows, 'rules': rules, 'rule_hash': rule_hash(rules), 'results': results,
                   'summary': summary(results), 'documents': documents or [], 'tolerance': tolerance}
        with self.connect() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run_id, now(), label, mode, json.dumps(payload)))
            db.execute('INSERT INTO audit(created,run_id,source_row,action,payload) VALUES(?,?,?,?,?)',
                       (now(), run_id, None, 'run_created', json.dumps({'rule_hash': payload['rule_hash'], 'mode': mode})))
        return run_id

    def runs(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,created,label,mode FROM runs ORDER BY created DESC')]

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise ValueError('Run not found')
        return {**dict(row), **json.loads(row['payload'])}

    def cases(self, run_id):
        with self.connect() as db:
            return {r['source_row']: dict(r) for r in db.execute('SELECT * FROM cases WHERE run_id=?', (run_id,))}

    def save_case(self, run_id, source_row, status, owner, notes):
        if status not in ['Open', 'Investigating', 'Resolved', 'Accepted']:
            raise ValueError('Invalid case status')
        run = self.load(run_id)
        if not any(r['source_row'] == source_row for r in run['results']):
            raise ValueError('Case is not part of this run')
        if status in ['Resolved', 'Accepted'] and not notes.strip():
            raise ValueError('Resolution or acceptance requires a rationale')
        with self.connect() as db:
            previous = db.execute('SELECT * FROM cases WHERE run_id=? AND source_row=?', (run_id, source_row)).fetchone()
            db.execute('INSERT OR REPLACE INTO cases VALUES(?,?,?,?,?)', (run_id, source_row, status, owner, notes))
            db.execute('INSERT INTO audit(created,run_id,source_row,action,payload) VALUES(?,?,?,?,?)',
                       (now(), run_id, source_row, 'case_updated', json.dumps({'before':dict(previous) if previous else None,
                        'after': {'status':status, 'owner':owner, 'notes':notes}})))

    def audit(self, run_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM audit WHERE run_id=? ORDER BY id', (run_id,))]

    def log_ai(self, run_id, source_row, action, payload):
        with self.connect() as db:
            db.execute('INSERT INTO audit(created,run_id,source_row,action,payload) VALUES(?,?,?,?,?)',
                       (now(), run_id, source_row, action, json.dumps(payload)))


def csv_bytes(rows):
    stream = io.StringIO()
    if not rows:
        return b''
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        # Prevent formula execution when analysts open exported text in Excel.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v
                         for k, v in row.items()})
    return stream.getvalue().encode('utf-8-sig')


def export_bundle(store, run_id):
    run = store.load(run_id)
    cases = store.cases(run_id)
    flat = []
    for r in run['results']:
        c = cases.get(r['source_row'], {})
        flat.append({k:r[k] for k in ['source_row','policy_id','segment','status','recorded','expected','difference','rule_version']} |
                    {'issues': '; '.join(r['issues']), 'hypotheses': '; '.join(r['hypotheses']),
                     'case_status': c.get('status','Open'), 'owner':c.get('owner',''), 'notes':c.get('notes','')})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('reconciliation.csv', csv_bytes(flat))
        archive.writestr('rules.json', json.dumps(run['rules'], indent=2))
        archive.writestr('audit.json', json.dumps(store.audit(run_id), indent=2))
        archive.writestr('evidence.json', json.dumps(run['documents'], indent=2))
        archive.writestr('run.json', json.dumps({k:v for k,v in run.items() if k != 'payload'}, indent=2))
        archive.writestr('report.md', f'# Pricing investigation report\n\nRun: {run_id}\nMode: {run["mode"]}\nCreated: {run["created"]}\n\n'
                          + '\n'.join(f'- {k}: {v}' for k,v in run['summary'].items())
                          + '\n\nExposure includes only calculable discrepant records. Blocked and duplicate records are excluded. '
                          + 'Counterfactual explanations are hypotheses, not confirmed causes. Case closure does not change calculated exposure.\n')
    return stream.getvalue()
