"""Integrate complete daily mean discharge intervals under their stated unit and time basis."""

import argparse
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path

from science_substrate import canonical, exact, read_json


DAY = timedelta(days=1)
TABLE = 'https://pubs.usgs.gov/wdr/2002/pa-02-2/pdfs/01570500.pdf'


def integrate(record):
    basis=(record.get('quantity'),record.get('time_basis'),record.get('unit'),record.get('statistic'),record.get('day_seconds'))
    if basis!=('discharge','station daily record','ft3/s','daily_mean',86400):
        return {'status':'ABSTAIN_UNITS_OR_BASIS'}
    start,end=(date.fromisoformat(record[key]) for key in ('start','end'))
    count=(end-start).days+1
    if not 1<=count<=366:
        raise ValueError('DATE_INTERVAL')
    expected={str(start+days*DAY) for days in range(count)}
    rows=record['rows']
    days={row['day'] for row in rows}
    if days!=expected or len(rows)!=len(days):
        return {'status':'ABSTAIN_DAY_COVERAGE',
                'missing_dates':sorted(expected-days),'unrequested_dates':sorted(days-expected),
                'duplicate_count':len(rows)-len(days)}
    if any(row['quality']!='reported' or not row['witness'] for row in rows):
        return {'status':'ABSTAIN_UNQUALIFIED_RECORD'}
    rates=[exact(row['rate']) for row in rows]
    if any(value<0 for value in rates):
        raise ValueError('DISCHARGE_RANGE')
    total=sum(rates)
    cubic_feet=total*86400
    metres=cubic_feet*exact('0.3048')**3
    return {'status':'INTEGRATED_DAILY_MEANS','station':record['station'],'days':count,
            'daily_rate_sum':[total.numerator,total.denominator],
            'cubic_feet':[cubic_feet.numerator,cubic_feet.denominator],
            'cubic_metres':[metres.numerator,metres.denominator],
            'first_witness':min(rows,key=lambda row:row['day'])['witness'],
            'last_witness':max(rows,key=lambda row:row['day'])['witness'],'source':record['source'],
            'operational_decision':'ABSTAIN'}


def verify_report(record):
    answer=integrate(record)
    if record['source']!=TABLE or answer['status']!='INTEGRATED_DAILY_MEANS':
        raise ValueError('INAPPLICABLE_PUBLISHED_CONTROL')
    rate=Decimal(record['published_sum'])
    mean=Decimal(record['published_mean'])
    # Independent control uses the published aggregate, so it does not sum the
    # individually transcribed rates or reuse the integrated implementation.
    expected=rate*Decimal(86400)*Decimal('0.3048')**3
    if (mean*answer['days']!=rate or
            list(rate.as_integer_ratio())!=answer['daily_rate_sum'] or
            list(expected.as_integer_ratio())!=answer['cubic_metres']):
        raise ValueError('PUBLIC_AGGREGATE_DISAGREEMENT')
    return answer


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path)
    parser.add_argument('--published-control',action='store_true')
    args=parser.parse_args()
    rows=read_json(args.file)
    result=verify_report(rows) if args.published_control else integrate(rows)
    print(canonical(result).decode())
