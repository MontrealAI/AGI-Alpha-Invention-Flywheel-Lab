"""Strict autonomous CSV onboarding for the declared reconciliation contract."""
import csv
import io
import json
from pathlib import Path
import re
from .service import canonical, validate

MAX_FILE_BYTES=2_000_000
HEADERS={'invoices': ['id','customer','amount_cents','currency'], 'payments': ['id','customer','amount_cents','invoice_refs','currency']}


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('DUPLICATE_JSON_FIELD')
        result[key]=value
    return result


def strict_json(text):
    def nonfinite(value): raise ValueError('NONFINITE_JSON')
    return json.loads(text,object_pairs_hook=_unique_object,parse_constant=nonfinite)


def read_csv(path,table,currency):
    raw=Path(path).read_bytes()
    if len(raw)>MAX_FILE_BYTES or b'\x00' in raw: raise ValueError('CSV_SIZE_OR_NULL_BYTE')
    try:
        text=raw.decode('utf-8-sig')
        rows=list(csv.reader(io.StringIO(text,newline=''),strict=True))
    except (UnicodeDecodeError,csv.Error) as exc: raise ValueError('MALFORMED_CSV') from exc
    expected=HEADERS[table]
    if not rows or rows[0]!=expected: raise ValueError('EXACT_UNIQUE_CSV_HEADERS_REQUIRED')
    if not 1<=len(rows)-1<=1000: raise ValueError('BOUNDED_NONEMPTY_CSV_REQUIRED')
    records=[]
    for cells in rows[1:]:
        if len(cells)!=len(expected) or any(len(x)>20_000 for x in cells): raise ValueError('CSV_FIELD_COUNT_OR_SIZE')
        row=dict(zip(expected,cells))
        if row.pop('currency')!=currency or currency!='USD': raise ValueError('CSV_CURRENCY_MISMATCH')
        if re.fullmatch(r'[1-9][0-9]{0,14}',row['amount_cents']) is None: raise ValueError('EXPLICIT_POSITIVE_INTEGER_CENTS_REQUIRED')
        row['amount_cents']=int(row['amount_cents'])
        if table=='payments': row['invoice_refs']=strict_json(row['invoice_refs'])
        records.append(row)
    return records


def prepare_order(contract_path,invoices_csv,payments_csv):
    raw=Path(contract_path).read_bytes()
    if len(raw)>10_000: raise ValueError('CONTRACT_SIZE')
    contract=strict_json(raw.decode('utf-8'))
    if not isinstance(contract,dict) or set(contract)!={'order_id','scope','currency','require_complete'}: raise ValueError('EXPLICIT_CONTRACT_FIELDS_REQUIRED')
    if contract['currency']!='USD': raise ValueError('UNSUPPORTED_CONTRACT_CURRENCY')
    order=dict(contract)
    order['invoices']=read_csv(invoices_csv,'invoices',contract['currency'])
    order['payments']=read_csv(payments_csv,'payments',contract['currency'])
    return validate(order)


def prepare_delivery(contract_path,invoices_csv,payments_csv,output):
    order=prepare_order(contract_path,invoices_csv,payments_csv)
    target=Path(output);target.mkdir(parents=True,exist_ok=False)
    (target/'prepared-order.json').write_bytes(canonical(order))
    return order


def synthetic_exports(order,output):
    """Export authored source records; never claim an actual client export."""
    target=Path(output);target.mkdir(parents=True,exist_ok=False)
    contract={k:order[k] for k in ('order_id','scope','currency','require_complete')}
    (target/'contract.json').write_bytes(canonical(contract))
    for table,headers in HEADERS.items():
        with (target/(table+'.csv')).open('w',encoding='utf-8',newline='') as handle:
            writer=csv.writer(handle);writer.writerow(headers)
            for source in order[table]:
                row=dict(source,currency=source.get('currency',order['currency']))
                if table=='payments': row['invoice_refs']=json.dumps(row['invoice_refs'],separators=(',',':'))
                writer.writerow([row[key] for key in headers])
    return target
