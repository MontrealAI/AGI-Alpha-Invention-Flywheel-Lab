"""Read-only evidence review with an externally retained case identity.

Outputs are local, static and synthetic-only. The review neither reserves
capacity nor authorizes recovery, manufacturing, payment or publication of data.
"""
from __future__ import annotations
import argparse
from html import escape
import json
from pathlib import Path
import sys
from .checker import audit


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('non-finite JSON number: ' + value)


def load_json(path):
    if path.is_symlink():
        raise ValueError('symlinked evidence files are unsupported')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_object,
                      parse_constant=_constant)


def review_directory(path, expected_case_sha256):
    """Do not trust AUDIT.json or an earlier human-readable passport."""
    if path.is_symlink():
        raise ValueError('symlinked evidence directories are unsupported')
    return audit(load_json(path/'INPUT.json'), load_json(path/'HANDOFF.json'),
                 load_json(path/'PASSPORT.json'),
                 expected_case_sha256=expected_case_sha256)


def render_html(result):
    passed = result.get('verdict') == 'PASS_SYNTHETIC_ONLY'
    headline = 'A consistent handoff. Not a live guarantee.' if passed else 'Do not rely on this handoff.'
    status = 'SYNTHETIC CHECK PASSED' if passed else 'VERIFICATION FAILED'
    css_status = 'pass' if passed else 'fail'
    def safe(value):
        return escape(str(value), quote=True)
    rows = [
        ('Original scenario', result.get('case_binding','NOT ESTABLISHED')),
        ('Outstanding commitments', result.get('replayed_orders','NOT ESTABLISHED')),
        ('Units reconstructed', result.get('replayed_units','NOT ESTABLISHED')),
        ('Timing', 'Scenario input only; no measured delivery time'),
        ('Supplier capacity and permission', 'Authored declarations; not externally confirmed'),
        ('Customer delivery / payment', 'Not performed / no actual revenue'),
        ('Third-party certification', 'Not established'),
    ]
    table = ''.join('<tr><th scope="row">'+safe(k)+'</th><td>'+safe(v)+'</td></tr>' for k,v in rows)
    failures = ''.join('<li>'+safe(v)+'</li>' for v in result.get('failures',[]))
    findings = '<section><h2>What stopped acceptance</h2><ul>'+failures+'</ul></section>' if failures else ''
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>CONTINUITY Ω — Keep the promise</title>
<style>
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172739;background:#f5f7fa;line-height:1.6}
*{box-sizing:border-box}body{margin:0}main{max-width:950px;margin:auto;padding:38px 24px 60px}
header{background:#11263a;color:#fff;padding:36px;border-radius:16px}h1{font-size:clamp(2rem,5vw,3.3rem);line-height:1.1;margin:12px 0}h2{line-height:1.25}
.kicker{font-size:.8rem;letter-spacing:.15em}.lead{font-size:1.2rem}.badge{display:inline-block;padding:7px 13px;border-radius:6px;font-weight:750}
.pass{background:#d8efe7;color:#184f3b}.fail{background:#ffe0df;color:#852c25}section{background:white;border:1px solid #dce2e9;border-radius:12px;margin:20px 0;padding:24px}
table{border-collapse:collapse;width:100%;text-align:left}td,th{vertical-align:top;border-bottom:1px solid #e1e6eb;padding:12px 8px}th{width:43%}code{overflow-wrap:anywhere;font-size:.85rem}a{color:#194f8d}
.small{font-size:.9rem;color:#46596a}li{overflow-wrap:anywhere}@media(max-width:560px){main{padding:18px 12px}header,section{padding:20px}td,th{display:block;width:100%;padding:7px 0}th{border:0;padding-top:15px}}
@media print{body{background:white}main{padding:0}header{background:white;color:#172739;border:2px solid #172739}section{break-inside:avoid}a{color:inherit}}
</style></head><body><main>
<header><div class="kicker">CONTINUITY Ω / EVIDENCE REVIEW</div><h1>Keep the promise.</h1>
<p class="lead">Find what recovery missed. Check the route that could keep the business moving.</p>
<span class="badge '''+css_status+'">'+status+'''</span></header>
<section><h2>'''+safe(headline)+'''</h2>
<p>This review replays INPUT.json, HANDOFF.json and PASSPORT.json. It does not reuse a stored success badge.</p>
<table><caption class="small">What this exact review establishes—and what it does not.</caption><tbody>'''+table+'''</tbody></table></section>'''+findings+'''
<section><h2>What must happen before a real continuity promise</h2>
<p>A named customer and fallback provider must authorize the exercise. Source records, capacity and rights need independently confirmed custody. Actual delivery must meet the original specification and deadline. Costs, payment and outstanding obligations must be reconciled.</p>
<p>Two customers cannot both claim the same last production slot. This local handoff review does not reserve shared capacity or certify disaster-wide availability.</p></section>
<section><h2>Evidence identity</h2><p><strong>Case SHA-256</strong><br><code>'''+safe(result.get('case_sha256','NOT ESTABLISHED'))+'''</code></p>
<p class="small">A caller-held digest can detect replacement of the agreed scenario. It does not prove the scenario is true, current, authorized or independently sourced. Keep the trusted reference outside the package; a hash supplied by the package itself is not a trust anchor.</p></section>
<footer class="small">Research prototype · Separate checker code, same research authorship · No external services, telemetry, live recovery, manufacturing or payments</footer>
</main></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description='CONTINUITY Ω pinned synthetic evidence review')
    parser.add_argument('--in-dir', type=Path, required=True)
    parser.add_argument('--expected-case-sha256', required=True,
                        help='canonical case identity retained separately before construction')
    parser.add_argument('--report-dir', type=Path,
                        help='optional NEW directory for static HTML and review JSON')
    args = parser.parse_args(argv)
    if args.report_dir and (args.report_dir.exists() or args.report_dir.is_symlink()):
        parser.error('report directory must be new; earlier evidence is never overwritten')
    try:
        result = review_directory(args.in_dir, args.expected_case_sha256)
    except (OSError, ValueError, TypeError, RecursionError) as error:
        result = {'schema':'continuity-omega/audit-v1','verdict':'FAIL',
                  'failures':['UNREADABLE_OR_AMBIGUOUS_EVIDENCE'],
                  'failure_count':1,'reason':str(error),
                  'scope':'SYNTHETIC_ONLY; no authority'}
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=False)
        (args.report_dir/'REVIEW.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        (args.report_dir/'index.html').write_text(render_html(result),encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result['verdict']=='PASS_SYNTHETIC_ONLY' else 3

if __name__=='__main__':
    sys.exit(main())
