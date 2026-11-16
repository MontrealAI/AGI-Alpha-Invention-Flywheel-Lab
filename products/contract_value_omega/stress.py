"""Reproduce a 25,000-line SYNTHETIC enterprise-scale financial audit.

No private customer data, external API, paid services, spreadsheet runtime
or claim of real savings. Verifies candidate totals, credited amounts, payment
classification, source hashes and buyer-report extraction on generated inputs.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import tempfile

from . import core,run,verify


def write_csv(folder,name,columns,rows):
    with (folder/name).open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def generate(folder,n):
    if type(n) is not int or n<1000 or n>100000 or n%1000:
        raise ValueError("SYNTHETIC_COUNT_MUST_BE_1000_MULTIPLE_AND_WITHIN_LIMITS")
    vendors=20
    write_csv(folder,"contracts.csv",core.HEADERS["contracts.csv"],
              ([f"CT-{j}",f"PRIVATE-VENDOR-{j:02d}","SERVICE","CAD","2026-01-01",
                "2026-12-31","100.00",f"SYNTHETIC-CONTRACT-{j}:p1"] for j in range(vendors)))
    write_csv(folder,"usage.csv",core.HEADERS["usage.csv"],
              ([f"PRIVATE-VENDOR-{j:02d}","SERVICE","2026-09","CAD",n//vendors,
                f"SYNTHETIC-USAGE-{j}"] for j in range(vendors)))
    write_csv(folder,"invoices.csv",core.HEADERS["invoices.csv"],
              ([f"L-{i:06d}",f"I-{i:06d}",f"PRIVATE-VENDOR-{i%vendors:02d}",
                f"SUP-DOC-{i:06d}","2026-10-03","2026-09","SERVICE",1,
                "110.00" if i%100==0 else "100.00",
                "110.00" if i%100==0 else "100.00",
                "CAD",f"SYNTHETIC-INVOICE-{i}"] for i in range(n)))
    write_csv(folder,"payments.csv",core.HEADERS["payments.csv"],
              ([f"P-{i:06d}",f"I-{i:06d}",
                "110.00" if i%100==0 else "100.00","CAD",f"SYNTHETIC-AP-{i}"]
                for i in range(n) if i%250))
    write_csv(folder,"credits.csv",core.HEADERS["credits.csv"],
              ([f"CR-{i:06d}",f"L-{i:06d}","5.00","CAD",f"SYNTHETIC-CREDIT-{i}"]
               for i in range(n) if i%1000==0))


def execute(n=25000):
    with tempfile.TemporaryDirectory(prefix="contract-value-synthetic-") as tmp:
        root=Path(tmp)
        source=root/"input";source.mkdir()
        generate(source,n)
        result=core.audit(core.validate(source))
        out=root/"output"
        run.write(out,result)
        proof=verify.verify(source,out)
        expected_anomalies=n//100
        expected_credits=n//1000
        expected_unpaid_anomalies=n//500
        expected_gross=expected_anomalies*1000
        expected_net=expected_gross-expected_credits*500
        expected_unpaid=expected_unpaid_anomalies*1000-expected_credits*500
        expected_paid=expected_net-expected_unpaid
        cad=result["summary_by_currency"]["CAD"]
        assert cad["candidate_lines"]==expected_anomalies
        assert cad["gross_review_cents"]==expected_gross
        assert cad["net_review_cents"]==expected_net
        assert cad["paid_review_cents"]==expected_paid
        assert cad["unpaid_or_unclear_review_cents"]==expected_unpaid
        assert cad["realized_recoveries_cents"]==0
        assert proof["status"]=="PASS_SCOPED_BUYER_SCREEN_RECONCILIATION"
        return {"status":"PASS_SYNTHETIC_SCOPED_STRESS_REPLAY",
                "lines":n,"suppliers":20,"known_rate_anomalies":expected_anomalies,
                "net_review_cents":expected_net,"paid_review_cents":expected_paid,
                "unpaid_or_unclear_review_cents":expected_unpaid,
                "actual_collections_cents":0,
                "scope":"Synthetic fixed-price contracts; not buyer demand, benchmark leadership, or real refund."}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lines",type=int,default=25000)
    args=p.parse_args(argv)
    print(json.dumps(execute(args.lines),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
