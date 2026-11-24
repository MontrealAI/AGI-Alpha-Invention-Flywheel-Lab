"""Export, execute and evaluate the registered executable-knowledge comparison."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal
from time import perf_counter_ns

from bridge.output_schema import validate_output
from model_step import brief, object_schema, step
from native_experiment import NativeRefused, NativeUnavailable, require_worker, run
from science_reference import verified
from science_substrate import FIELDS, MEANINGS, calculate, canonical, fingerprint, positional, read_json


ARMS = ('direct','harness','typed')
TASK = (
    'Implement a portable pure-Python function solve(case) for a linear transit ephemeris decision. '
    'Use exact decimal arithmetic. Find the integer epoch of the first model center at or after anchor, '
    'including negative epochs. The center at epoch n is T0 + n P. With the two stated marginal standard '
    'deviations, consider every correlation between -1 and 1. Report outward-rounded integer seconds '
    'for the minimum and maximum possible propagated model standard deviation. Compare the unrounded '
    'values with one twelfth of nominal duration. Use WITHIN if even the upper bound is at most target, '
    'EXCEEDS if the lower bound is above target, otherwise COVARIANCE_SENSITIVE. The witness must exactly '
    'echo the input source locator. For basis other than BJD_TDB or missing anchor, use ABSTAIN_TIME_BASIS; '
    'for missing numeric fields use ABSTAIN_MISSING. Both abstentions use null epoch and sigma_s. '
    'Output from solve is the object with exactly decision, epoch, sigma_s, witness. Use standard library; '
    'execution is isolated, one case at a time, without other evidence files or network. '
    'Return only a JSON object with one string field source, containing the complete implementation.'
)
HARNESS = ('Work as a scientific constructor under HARNESS. Identify the research hypothesis, review the '
           'development examples, construct a bounded artifact, inspect the supplied interface carefully '
           'and produce an executable implementation that will be independently evaluated.\n')
CODE = object_schema({'source':brief(5000)})


def projection(value, arm):
    return value if arm == 'typed' else positional(value)


def body(dev_path, arm):
    data=read_json(dev_path)
    if arm == 'typed':
        layout={'encoding':'named numeric fields under ephemeris','fields':MEANINGS}
    else:
        layout={'encoding':'five position values in row','order':list(FIELDS),
                'descriptions':[[name,*MEANINGS[name]] for name in FIELDS]}
    examples=[{'input':projection(row['input'],arm),'expected':row['expected']} for row in data]
    return (HARNESS if arm=='harness' else '')+TASK+'\n'+canonical({'contract':layout,'examples':examples}).decode()


def write(path, value):
    with Path(path).open('xb') as handle:
        handle.write(canonical(value)+b'\n')


def packet(args):
    prompt=body(args.development,args.arm)
    document={'schema':'frontier/manual-science-packet-v1','arm':args.arm,'prompt':prompt,
              'authority':'public evidence only; local offline Python; bounded native evaluator',
              'source':'Kokori et al. (2026), ApJS 283, 5, Table 8, doi:10.3847/1538-4365/ae3238',
              'development_sha256':sha256(args.development.read_bytes()).hexdigest(),
              'transport':'operator-reviewed manual handoff; account or model claims are self-reported'}
    write(args.output,{**document,'packet_sha256':fingerprint(document)})


def constructed(args):
    require_worker()
    prompt=body(args.development,args.arm)
    result=step(args.workspace,args.config,args.model,CODE,prompt,'substrate-'+args.arm,args.tokens,attempts=1,
                deadline=args.until)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))


def import_candidate(args):
    document=read_json(args.packet)
    token=document.pop('packet_sha256')
    response=read_json(args.response)
    if (document.get('schema')!='frontier/manual-science-packet-v1' or token!=fingerprint(document)
            or set(response)!={'packet_sha256','source','author'} or response['packet_sha256']!=token
            or type(response['author']) is not str or not 0<len(response['author'])<=120):
        raise ValueError('HANDOFF_BINDING')
    validate_output({'source':response['source']},CODE)
    write(args.output,{'status':'SEALED','result':{'source':response['source']},'binding':{
        'kind':'operator-assisted','author':response['author'],'packet_sha256':token,
        'response_sha256':sha256(args.response.read_bytes()).hexdigest()},'events':[]})


def outcome(actual, expected, ran):
    if not ran:
        return 'NO_CANDIDATE'
    if 'error' in actual:
        return 'EXECUTION_ERROR'
    result=actual.get('result')
    if type(result) is not dict or set(result)!=set(expected):
        return 'OUTPUT_INTERFACE'
    if result['witness']!=expected['witness']:
        return 'WITNESS'
    if result['decision']!=expected['decision']:
        return 'ABSTENTION' if expected['decision'].startswith('ABSTAIN') else 'DECISION'
    if canonical(result['epoch'])!=canonical(expected['epoch']):
        return 'EPOCH'
    return 'ACCEPT' if canonical(result['sigma_s'])==canonical(expected['sigma_s']) else 'UNIT_OR_UNCERTAINTY'


def evaluate(args):
    require_worker()
    candidate=read_json(args.candidate)
    artifact=candidate.get('result') if candidate.get('status')=='SEALED' else None
    if artifact:
        validate_output(artifact,CODE)
    decision=Counter()
    deliver=[]
    sources=Counter()
    successes=Counter()
    unsafe=0
    unsupported=0
    for label, record in enumerate(read_json(args.confirmation),1):
        case, expected = record['input'], record['expected']
        if calculate(case)!=expected or verified(case)!=expected:
            raise ValueError('INDEPENDENT_REFERENCE_MISMATCH')
        start=perf_counter_ns()
        observed={}
        if artifact:
            try:
                observed=run(artifact['source'],projection(case,args.arm))
            except NativeUnavailable:
                raise
            except NativeRefused as error:
                observed={'error':str(error)}
        category=outcome(observed,expected,bool(artifact))
        decision[category]+=1
        source=record.get('origin','development')
        sources[source]+=1
        successes[source]+=category=='ACCEPT'
        returned=observed.get('result')
        if type(returned) is dict and returned.get('decision')=='WITHIN' and expected['decision']!='WITHIN':
            unsafe+=1
        if (category!='ACCEPT' and type(returned) is dict
                and returned.get('decision') in ('WITHIN','EXCEEDS','COVARIANCE_SENSITIVE')):
            unsupported+=1
        deliver.append({'index':label,'origin':source,'category':category,'work_ns':perf_counter_ns()-start,
                        'observed':observed})
    print(canonical({'arm':args.arm,'input_sha256':sha256(args.confirmation.read_bytes()).hexdigest(),
          'candidate_sha256':sha256(args.candidate.read_bytes()).hexdigest(),'outcomes':dict(decision),
          'source_denominators':dict(sources),'source_accepted':dict(successes),
          'unsupported_within':unsafe,'unsupported_decisions':unsupported,'records':deliver}).decode())


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    pack=sub.add_parser('packet')
    pack.add_argument('--development',type=Path,required=True)
    pack.add_argument('--output',type=Path,required=True)
    pack.add_argument('--arm',choices=ARMS,default='direct')
    pack.set_defaults(action=packet)
    build=sub.add_parser('construct')
    for flag in ('development','workspace','config'):
        build.add_argument('--'+flag,type=Path,required=True)
    build.add_argument('--arm',choices=ARMS,required=True)
    build.add_argument('--model',required=True)
    build.add_argument('--until',type=int,required=True)
    build.add_argument('--tokens',type=int,default=1050)
    build.set_defaults(action=constructed)
    receive=sub.add_parser('import')
    for flag in ('packet','response','output'):
        receive.add_argument('--'+flag,type=Path,required=True)
    receive.set_defaults(action=import_candidate)
    evaluate_cmd=sub.add_parser('evaluate')
    for flag in ('candidate','confirmation'):
        evaluate_cmd.add_argument('--'+flag,type=Path,required=True)
    evaluate_cmd.add_argument('--arm',choices=ARMS,required=True)
    evaluate_cmd.set_defaults(action=evaluate)
    args=parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        args.action(args)
    except KeyboardInterrupt:
        parser.exit(130,'Paused. Reopen the same workspace, model configuration, and study.\n')


if __name__=='__main__':
    main()
