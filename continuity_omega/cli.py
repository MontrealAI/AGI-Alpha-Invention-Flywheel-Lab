"""CLI for isolated synthetic tests; never submit data to a remote service."""
import argparse, json, sys
from pathlib import Path
from .demo import case_for,CASES
from .engine import construct,DrillRejected
from .checker import audit
from .review import load_json, render_html

def _json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def main(argv=None):
    ap=argparse.ArgumentParser(prog='continuity-omega',description='CONTINUITY Ω synthetic business-promise recovery audit; no network or real authority')
    sub=ap.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('demo',help='execute synthetic scenario in NEW directory')
    a.add_argument('--case',choices=CASES,default='nominal');a.add_argument('--out',type=Path,required=True)
    b=sub.add_parser('verify',help='independently replay local drill artifacts')
    b.add_argument('--in-dir',type=Path,required=True)
    b.add_argument('--expected-case-sha256', help='optional case identity held outside the package')
    c=sub.add_parser('inspect',help='read local passport without changing it')
    c.add_argument('--in-dir',type=Path,required=True)
    c.add_argument('--expected-case-sha256', help='optional case identity held outside the package')
    opts=ap.parse_args(argv)
    if opts.cmd=='demo':
        out=opts.out.resolve(strict=False)
        if out.exists():ap.error('output directory must not already exist; prevents overwriting prior evidence')
        out.mkdir(parents=True)
        case=case_for(opts.case)
        _json(out/'INPUT.json',case)
        try:handoff,passport=construct(case)
        except DrillRejected as err:
            receipt={'schema':'continuity-omega/rejection-v1','exercise_id':case.get('exercise_id'),
                'verdict':'REJECTED_BEFORE_HANDOFF','reason':str(err),
                'scope':'SYNTHETIC_ONLY; incurred real costs and customer consequences NOT measured'}
            _json(out/'REJECTION.json',receipt)
            print(json.dumps(receipt,indent=2));return 2
        _json(out/'HANDOFF.json',handoff);_json(out/'PASSPORT.json',passport)
        result=audit(case,handoff,passport);_json(out/'AUDIT.json',result)
        text=f'''# CONTINUITY Ω — Continuity Passport\n\n**Exercise:** {case['exercise_id']}  \n**Evidence type:** AUTHORED SYNTHETIC SCENARIO (not a measured recovery exercise)  \n**Independent code check:** {result['verdict']}  \n**Commercial status:** MODEL ONLY, NO REAL BUYER OR SUPPLIER  \n\n## What the restored system missed\n'''
        for issue in passport['restoration_findings']:
            text+=f"- `{issue['order_id']}`: {issue['issue']}\n"
        text+=f'''\n## What we constructed\n\n- {len(handoff['orders'])} outstanding orders, {handoff['required_units']} units\n- Simulated provider `{handoff['supplier_id']}` with capacity and a {handoff['rehearsed_completion_hours']}-hour modeled lead time\n- Required completion in {handoff['latest_required_hours']} hours\n- Model quote ${passport['economics']['offer']:,}; full modeled cost ${passport['economics']['modeled_cost']:,}; modeled contribution ${passport['economics']['modeled_contribution']:,}\n- Reconciliation and authorization: real-world outcomes **NOT ESTABLISHED**\n\n## Next possibility\n\n{passport['successor_hypothesis']}\n\n## Decision\n\n**{result['verdict']}** is the current decision. A PASS_SYNTHETIC_ONLY verdict means the sealed authored inputs and generated package passed the local separate checker. It does not prove live cyber recovery, accepted supplier capacity, customer consent, payment, or resilience against real attacks. It does not show superiority to a competent conventional solution.\n\nThe next valid test is a permissioned rehearsal with real, separately evidenced source records, supplier terms, independent customer acceptance, complete costs, and an eligible matched conventional comparator.\n'''
        (out/'PASSPORT.md').write_text(text,encoding='utf-8')
        (out/'PASSPORT.html').write_text(render_html(result),encoding='utf-8')
        print(json.dumps({'directory':str(out),'verdict':result['verdict'],'orders':len(handoff['orders']),
            'units':handoff['required_units'],'restore_findings':len(passport['restoration_findings'])},indent=2))
        return 0 if result['verdict']=='PASS_SYNTHETIC_ONLY' else 3
    path=opts.in_dir
    try:
        if path.is_symlink():
            raise ValueError('symlinked evidence directory is unsupported')
        case=load_json(path/'INPUT.json')
        handoff=load_json(path/'HANDOFF.json')
        passport=load_json(path/'PASSPORT.json')
        verdict=audit(case,handoff,passport,
                      expected_case_sha256=opts.expected_case_sha256)
    except (OSError,ValueError,TypeError,RecursionError) as e:
        print(json.dumps({'verdict':'FAIL','reason':str(e)}));return 3
    if opts.cmd=='inspect':
        # Display fresh validation, not a potentially stale stored success badge.
        print(json.dumps({'fresh_audit':verdict,'passport':passport},indent=2))
    else:
        print(json.dumps(verdict,indent=2))
    return 0 if verdict['verdict']=='PASS_SYNTHETIC_ONLY' else 3

if __name__=='__main__':sys.exit(main())
