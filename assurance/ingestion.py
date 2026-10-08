import io
from datetime import datetime
import pandas as pd


def read_portfolio(data, name, sheet=None):
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Portfolio exceeds 20 MB')
    if name.lower().endswith('.xlsx'):
        frame = pd.read_excel(io.BytesIO(data), sheet_name=sheet if sheet is not None else 0, dtype=str).fillna('')
    else:
        frame = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    if len(frame) > 100000:
        raise ValueError('Portfolio exceeds 100,000 rows; split into batches')
    return frame


def map_records(frame, mapping):
    rows = []
    for source in frame.to_dict('records'):
        record = {field:source.get(column,'') for field,column in mapping.items()}
        # Excel's date-typed cells stringify as midnight timestamps. Preserve the
        # calendar date only for this unambiguous shape; never guess local formats.
        value = str(record.get('renewal_date',''))
        if len(value) == 19 and value.endswith(' 00:00:00'):
            try:
                record['renewal_date'] = datetime.strptime(value,'%Y-%m-%d %H:%M:%S').date().isoformat()
            except ValueError:
                pass
        rows.append(record)
    return rows
