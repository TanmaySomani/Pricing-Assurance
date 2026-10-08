import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from assurance.ai import explain, extract_records
from assurance.documents import read_document, search_evidence
from assurance.engine import FIELDS, reconcile, validate_rules
from assurance.ingestion import read_portfolio, map_records
from assurance.storage import Store, csv_bytes, export_bundle
from assurance.synthetic import generate

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Pricing Assurance | Workbench', page_icon='◈', layout='wide')
st.markdown('''<style>
.stApp {background:#f6f7f9} h1,h2,h3 {letter-spacing:-.035em}
[data-testid="stMetric"] {background:white;padding:18px;border:1px solid #e2e6ed;border-radius:12px}
[data-testid="stMetricValue"] {font-size:1.2rem}
[data-testid="stSidebar"] {background:#eaf0f5}
.eyebrow {font-size:12px;letter-spacing:.16em;color:#52717c;font-weight:700}
</style>''', unsafe_allow_html=True)
store = Store(os.getenv('ASSURANCE_DB', str(ROOT / 'data/workbench.sqlite3')))


def error(exc):
    # Avoid printing provider responses, credentials, or entire source files.
    if isinstance(exc, (ValueError, KeyError, UnicodeError)):
        st.error(str(exc))
    else:
        st.error(f'{type(exc).__name__}: operation failed. Check the file format or local API settings and retry. No run was saved.')


def table(results, cases):
    return pd.DataFrame([{'Row':r['source_row'], 'Policy':r['policy_id'], 'Segment':r['segment'],
                         'Finding':r['status'], 'Recorded':float(r['recorded']) if r['recorded'] else None,
                         'Expected':float(r['expected']) if r['expected'] else None,
                         'Difference':float(r['difference']) if r['difference'] else None,
                         'Case':cases.get(r['source_row'],{}).get('status','Open'),
                         'Issues':'; '.join(r['issues']), 'Hypotheses':'; '.join(r['hypotheses'])} for r in results])


with st.sidebar:
    st.markdown('### ◈ Assurance')
    st.caption('INSURANCE PRICING WORKBENCH')
    page = st.radio('Workspace', ['Overview', 'Import & reconcile', 'Investigations', 'Evidence & documents', 'Rules & settings'])
    runs = store.runs()
    if runs:
        options = {r['id']: f'{r["label"]} · {r["created"][:16]}' for r in runs}
        current = st.session_state.get('run_id')
        selected = st.selectbox('Saved run', list(options), index=list(options).index(current) if current in options else 0,
                                format_func=lambda x:options[x])
        st.session_state['run_id'] = selected
    st.divider()
    st.caption('Local storage · AUD · Single analyst')
    st.caption('AI ready' if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL') else 'OpenAI not configured')

st.markdown('<p class="eyebrow">DETECT / EXPLAIN / QUANTIFY / ACT</p>', unsafe_allow_html=True)
st.title(page)
run = store.load(st.session_state['run_id']) if runs else None

if page == 'Overview':
    st.write('Find incorrect renewal premiums. Follow the calculation. Build an evidence-backed investigation.')
    if not run:
        st.info('Start with a reproducible synthetic portfolio, or import your own renewal records and rating rules.')
        if st.button('Create 20,000-policy demo', type='primary'):
            with st.spinner('Generating and reconciling the synthetic portfolio…'):
                rules = json.loads((ROOT / 'examples/rules.json').read_text())
                rows, _ = generate(rules)
                results = reconcile(rows, rules)
                st.session_state['run_id'] = store.save_run('Motor renewal demo', 'synthetic', rows, rules, results)
            st.rerun()
    else:
        st.info('SYNTHETIC DEMONSTRATION — financial figures are simulated exposure.' if run['mode'] == 'synthetic'
                else 'REAL DATA — results depend on the reviewed input fields and supplied rating contract.')
        s = run['summary']
        cols = st.columns(4)
        for col, label, value in zip(cols, ['Affected policies','Overcharges','Undercharges','Blocked records'],
                                     [f'{s["affected"]:,}', f'A${float(s["overcharges"]):,.2f}', f'A${float(s["undercharges"]):,.2f}', f'{s["blocked"]:,}']):
            col.metric(label,value)
        st.caption(f'{s["calculable"]:,} calculable / {s["rows"]:,} input rows · {s["discrepancy_rate"]:.1%} discrepancy rate · tolerance A${run["tolerance"]}')
        frame = table(run['results'], store.cases(run['id']))
        left,right = st.columns([1,1.6])
        with left:
            st.subheader('Exposure by segment')
            flagged = frame[frame.Finding == 'discrepancy'].copy()
            if len(flagged):
                flagged['Absolute difference'] = flagged.Difference.abs()
                st.bar_chart(flagged.groupby('Segment')['Absolute difference'].sum(), color='#16827d')
            else:
                st.success('No calculable discrepancies above tolerance.')
        with right:
            st.subheader('Investigation priorities')
            priority = frame[frame.Finding != 'matched'].copy()
            priority['impact'] = priority.Difference.abs()
            st.dataframe(priority.sort_values('impact',ascending=False).head(10)[['Policy','Difference','Finding','Segment','Case']],
                         hide_index=True, width='stretch',
                         column_config={'Difference': st.column_config.NumberColumn('Difference (AUD)',format='%.2f')})
        st.download_button('Download full investigation bundle', export_bundle(store,run['id']), 'investigation.zip', 'application/zip')
        st.caption('Exposure excludes blocked records. Positive difference = overcharge. Case closure does not change historical totals.')

elif page == 'Import & reconcile':
    st.write('Load a policy CSV/Excel file or use reviewed document records, then supply the applicable pricing rules.')
    method = st.radio('Input source', ['CSV / Excel', 'Reviewed document records'], horizontal=True)
    rows = None
    if method == 'CSV / Excel':
        uploaded = st.file_uploader('Renewal portfolio', type=['csv','xlsx'])
        if uploaded:
            try:
                if uploaded.size > 20*1024*1024:
                    raise ValueError('Portfolio exceeds 20 MB')
                if uploaded.name.lower().endswith('.xlsx'):
                    sheets = pd.ExcelFile(io.BytesIO(uploaded.getvalue())).sheet_names
                    sheet = st.selectbox('Worksheet', sheets)
                    frame = read_portfolio(uploaded.getvalue(), uploaded.name, sheet)
                else:
                    frame = read_portfolio(uploaded.getvalue(), uploaded.name)
                if len(frame) > 100000:
                    raise ValueError('Portfolio exceeds 100,000 rows; split into batches')
                st.caption(f'{len(frame):,} records · Map your columns to the calculation contract.')
                mapping = {}
                for field in FIELDS:
                    options = ['(not supplied)'] + list(frame.columns)
                    mapping[field] = st.selectbox(field, options, index=options.index(field) if field in options else 0, key=f'map_{field}')
                chosen = [v for v in mapping.values() if v != '(not supplied)']
                if len(chosen) != len(set(chosen)):
                    st.error('Each source column may map to only one field.')
                else:
                    rows = map_records(frame, mapping)
                    st.dataframe(pd.DataFrame(rows).head(20), hide_index=True)
            except Exception as exc:
                error(exc)
    else:
        rows = st.session_state.get('reviewed_records')
        if rows is None:
            st.info('Extract and approve records in Evidence & documents first.')
        else:
            st.dataframe(pd.DataFrame(rows), hide_index=True)
    rules_file = st.file_uploader('Verified rating rules JSON (required for real data)', type=['json'])
    rules = None
    if rules_file:
        try:
            rules = validate_rules(json.loads(rules_file.getvalue()))
            st.success(f'{len(rules["versions"])} versioned rules validated')
            st.json(rules, expanded=False)
        except Exception as exc:
            error(exc)
    label = st.text_input('Run label', 'Renewal pricing review')
    mode = st.selectbox('Data classification', ['real', 'synthetic'],
                        help='Use synthetic for examples, generated data and demonstrations.')
    tolerance = st.text_input('Discrepancy tolerance (AUD)', '0.01')
    confirm = st.checkbox('I reviewed the mapped data, pricing formula, rule sources and effective dates.')
    if st.button('Reconcile and save run', type='primary', disabled=not(rows and rules and confirm and label.strip())):
        try:
            with st.spinner('Validating and calculating…'):
                results = reconcile(rows, rules, tolerance)
                st.session_state['run_id'] = store.save_run(label, mode, rows, rules, results,
                    st.session_state.get('documents', []), tolerance)
            st.success('Run saved. Open Overview or Investigations to review findings.')
            st.rerun()
        except Exception as exc:
            error(exc)
    st.download_button('Download CSV template', csv_bytes([dict.fromkeys(FIELDS,'')]), 'policy_template.csv', 'text/csv')

elif page == 'Investigations':
    if not run:
        st.info('Create or import a run first.')
    else:
        cases = store.cases(run['id'])
        frame = table(run['results'], cases)
        a,b,c = st.columns(3)
        findings = a.multiselect('Finding', ['discrepancy','blocked','matched'], default=['discrepancy','blocked'])
        segments = b.multiselect('Segment', sorted(frame.Segment.unique()))
        query = c.text_input('Policy contains')
        case_filter = st.multiselect('Case status', ['Open','Investigating','Resolved','Accepted'])
        filtered = frame[frame.Finding.isin(findings)]
        if segments:
            filtered = filtered[filtered.Segment.isin(segments)]
        if query:
            filtered = filtered[filtered.Policy.str.contains(query,case=False,regex=False)]
        if case_filter:
            filtered = filtered[filtered.Case.isin(case_filter)]
        filtered = filtered.assign(impact=filtered.Difference.abs()).sort_values('impact',ascending=False).drop(columns='impact')
        st.dataframe(filtered,hide_index=True,width='stretch')
        st.download_button('Export filtered cohort', csv_bytes(filtered.to_dict('records')), 'cohort.csv','text/csv')
        if len(filtered):
            row_num = st.selectbox('Inspect case', list(filtered.Row), format_func=lambda n:f'Row {n} · {frame.loc[frame.Row == n,"Policy"].iloc[0]}')
            result = next(r for r in run['results'] if r['source_row'] == row_num)
            st.subheader(f'Policy {result["policy_id"]}')
            x,y = st.columns(2)
            with x:
                st.markdown('**Verified calculation**')
                st.json(result['breakdown'] or {'blocked':result['issues']})
                st.write('Applicable version:',result['rule_version'] or 'Unavailable')
                for issue in result['issues']:
                    st.warning(issue)
                for hypothesis in result['hypotheses']:
                    st.info(hypothesis)
            with y:
                st.markdown('**Original source record**')
                st.json(result['source'])
                active = next((v for v in run['rules']['versions'] if v['version'] == result['rule_version']), None)
                if active:
                    st.json(active,expanded=False)
            saved = cases.get(row_num, {})
            with st.form(f'case_{run["id"]}_{row_num}'):
                states = ['Open','Investigating','Resolved','Accepted']
                state = st.selectbox('Investigation status',states,index=states.index(saved.get('status','Open')))
                owner = st.text_input('Analyst',saved.get('owner',''))
                notes = st.text_area('Evidence, actions and resolution rationale',saved.get('notes',''))
                if st.form_submit_button('Save investigation'):
                    try:
                        store.save_case(run['id'],row_num,state,owner,notes)
                        st.success('Investigation and audit entry saved.')
                    except Exception as exc:
                        error(exc)
            st.markdown('**AI investigation draft**')
            evidence = search_evidence(run['documents'],f'{result["policy_id"]} {result["segment"]} discount {result["rule_version"]}')
            with st.expander('Context that will be sent to OpenAI'):
                st.json({'result':result, 'rules':run['rules'], 'retrieved_evidence':evidence})
            consent = st.checkbox('Send the displayed calculation, source fields, rules and evidence to OpenAI.', key=f'consent_{row_num}')
            if st.button('Draft explanation', disabled=not consent):
                try:
                    with st.spinner('Drafting from verified results…'):
                        draft,meta = explain(result,run['rules'],evidence)
                    store.log_ai(run['id'],row_num,'ai_explanation',{'draft':draft,**meta})
                    st.session_state[f'draft_{run["id"]}_{row_num}'] = draft
                except Exception as exc:
                    error(exc)
            if st.session_state.get(f'draft_{run["id"]}_{row_num}'):
                st.markdown(st.session_state[f'draft_{run["id"]}_{row_num}'])
                st.caption('AI draft — verify citations and conclusions before using it.')
        with st.expander('Audit history'):
            st.dataframe(pd.DataFrame(store.audit(run['id'])),hide_index=True)

elif page == 'Evidence & documents':
    st.write('Attach pricing manuals, renewal notices or policy schedules. Review extracted records before reconciliation.')
    uploads = st.file_uploader('Evidence files', type=['pdf','docx','txt','md'], accept_multiple_files=True)
    if st.button('Read documents locally', disabled=not uploads):
        try:
            documents = [read_document(u.name,u.getvalue()) for u in uploads]
            if len({d['name'] for d in documents}) != len(documents):
                raise ValueError('Use unique filenames for unambiguous evidence citations')
            st.session_state['documents'] = documents
            st.session_state.pop('extraction',None)
            st.session_state.pop('reviewed_records',None)
            st.success('Evidence read locally. Save it with a reconciliation run to retain it across sessions.')
        except Exception as exc:
            error(exc)
    documents = st.session_state.get('documents', run['documents'] if run else [])
    for doc in documents:
        with st.expander(f'{doc["name"]} · {doc["sha256"][:12]}'):
            if doc['empty_pages']:
                st.warning('No readable text in: '+', '.join(doc['empty_pages'])+'. Scanned pages require OCR before extraction; they are not silently processed.')
            for chunk in doc['chunks']:
                st.caption(chunk['locator'])
                st.text(chunk['text'])
    query = st.text_input('Search document evidence')
    if query:
        for match in search_evidence(documents,query):
            st.caption(f'{match["name"]} · {match["locator"]}')
            st.text(match['text'])
    st.divider()
    st.subheader('Extract policy records with OpenAI')
    st.caption('Text PDF, DOCX and TXT extraction; uploaded evidence text is sent only when you request it. Large portfolios should use CSV/Excel.')
    consent = st.checkbox('Send the readable evidence text shown above to OpenAI for draft extraction.')
    if st.button('Extract draft records',disabled=not(documents and consent)):
        try:
            if any(d['empty_pages'] for d in documents):
                raise ValueError('One or more pages have no readable text. OCR or remove those documents before extraction.')
            with st.spinner('Extracting cited records…'):
                parsed,meta = extract_records(documents)
            st.session_state['extraction'] = parsed
            st.session_state['documents'] = documents
            st.session_state.pop('reviewed_records', None)
            st.caption(f'Extraction model: {meta["model"]}')
        except Exception as exc:
            error(exc)
    extraction = st.session_state.get('extraction')
    if extraction:
        for warning in extraction['warnings']:
            st.warning(str(warning))
        if extraction['records']:
            edited = st.data_editor(pd.DataFrame(extraction['records']),hide_index=True,num_rows='dynamic',key='document_editor')
            checked = st.checkbox('I checked every imported field and source citation. Blank fields remain unknown.')
            if st.button('Approve records for import',disabled=not checked):
                st.session_state['reviewed_records'] = edited.fillna('').astype(str).to_dict('records')
                st.success('Records approved. Open Import & reconcile and choose Reviewed document records.')
        else:
            st.info('No policy records found. A pricing manual can support rules without containing policy records.')

elif page == 'Rules & settings':
    st.write('Pricing rules are explicit, versioned and reviewed. The sample contract is fictional and must be replaced for real data.')
    st.code('rated = round(base_rate[segment] × risk_factor, 2)\ndiscounted = round(rated × (1 − discount_rate), 2)\ntax = round((discounted + fee) × tax_rate, 2)\nexpected = discounted + fee + tax',language='text')
    st.caption('Decimal arithmetic · ROUND_HALF_UP · effective dates inclusive · annual AUD premium · no midterm adjustments')
    sample = (ROOT / 'examples/rules.json').read_text()
    st.download_button('Download sample rule schema',sample,'rules.json','application/json')
    st.json(json.loads(sample),expanded=False)
    st.warning('This formula does not represent every insurer. If your rules include caps, levies, instalments, other taxes or different rounding, extend and test the engine before using its figures.')
    st.code('OPENAI_API_KEY=\nOPENAI_MODEL=\nASSURANCE_DB=data/workbench.sqlite3',language='text')
    st.caption('Set these values in the project .env and restart. Credentials never belong in policy records or uploaded files.')
    st.write('See README.md, BUILD_PROGRESS.md and docs/PRICING_CONTRACT.md for setup, supported inputs and resumable stages.')
