"""Construct and verify compact exact-arithmetic science artifacts."""

import argparse
import ast
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from math import ceil, floor
import operator
from pathlib import Path
import signal
from time import time

from bridge.output_schema import prepare_schema, validate_output
from model_step import Constructor, brief, object_schema, step
from pages import digest
from research import ResearchRun
from science_reference import verified
from science_substrate import FIELDS, MEANINGS, calculate, canonical, exact, fingerprint, positional, read_json, typed_fields
from study import lock


ARMS = ('direct', 'harness', 'typed')
OUTPUTS = ('epoch', 'low', 'high', 'limit')
IDENT = ('a', 't', 'u', 'p', 'v', 'd')
SCHEMA = object_schema({name:brief(96) for name in OUTPUTS})
INVESTIGATION = object_schema({key:brief(210) for key in ('question','missing_evidence','decisive_test','beneficiary')})
BINARY = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv}
FUNCTIONS = {'abs':abs, 'ceil':ceil, 'floor':floor}
TASK = (
    'Construct a transit ephemeris decision as four short exact arithmetic expressions. '
    'The expression variables are a=anchor day, t=reference midpoint day, p=orbital period days, '
    'u=reference midpoint marginal standard deviation days, v=period marginal standard deviation days, '
    'd=nominal duration hours, and n=the integer from the epoch expression. '
    'Use Python expression syntax, integers, + - * /, abs, ceil, floor, and parentheses. '
    'Return one JSON object with string fields epoch, low, high, limit. No explanation or code fence. '
    'epoch gives the first linear-model center at or after a, including negative epochs. '
    'low and high bound the propagated time standard deviation in seconds across all admissible correlations. '
    'limit is the unrounded target in seconds, one twelfth of nominal duration. '
    'Leave rounding, source witness, missing fields, time basis checks and classification to the evaluator.'
)
HARNESS = ('Use the existing scientific HARNESS process. Review the hypothesis, inspect the interface, '
           'check the development examples, and return a bounded executable proposal.\n')
FEEDBACK = ('The first attempt copied example numbers or returned unsupported expression syntax. '
            'The returned strings will be parsed as formulas and run on different numbers. '
            'Write expressions with the variable names a, t, p, u, v, d, n exactly as defined above. '
            'The example outputs are checks of those formulas. Do not put a worked example answer in a formula.\n')


def compile_node(node, allowed):
    if type(node) is ast.Constant and type(node.value) is int and 0 <= node.value <= 100_000:
        return ('integer', node.value)
    if type(node) is ast.Name and node.id in allowed:
        return ('binding', node.id)
    if type(node) is ast.BinOp and type(node.op) in BINARY:
        return (BINARY[type(node.op)], compile_node(node.left, allowed), compile_node(node.right, allowed))
    if type(node) is ast.UnaryOp and type(node.op) is ast.USub:
        return (operator.neg, compile_node(node.operand, allowed))
    if (type(node) is ast.Call and type(node.func) is ast.Name and node.func.id in FUNCTIONS
            and len(node.args)==1 and not node.keywords):
        return (FUNCTIONS[node.func.id], compile_node(node.args[0], allowed))
    raise ValueError('EXPRESSION_CONTRACT')


def programs(source):
    validate_output(source, SCHEMA)
    return {name:compile_node(ast.parse(source[name], mode='eval').body,
                              set(IDENT) if name=='epoch' else {*IDENT,'n'}) for name in OUTPUTS}


def execute(expression, values):
    op, *args = expression
    if op=='integer':
        return Fraction(args[0])
    if op=='binding':
        return values[args[0]]
    return Fraction(op(*(execute(node,values) for node in args)))


def project(candidate, case):
    fields = typed_fields(case)
    witness = case['witness']
    withheld = {'epoch':None, 'sigma_s':None, 'witness':witness}
    if case['basis']!='BJD_TDB' or case['anchor'] is None:
        return {**withheld,'decision':'ABSTAIN_TIME_BASIS'}
    if any(item is None for item in fields):
        return {**withheld,'decision':'ABSTAIN_MISSING'}
    quantities = dict(zip(IDENT,map(exact,[case['anchor'],*fields]),strict=True))
    epoch = execute(candidate['epoch'],quantities)
    if epoch.denominator!=1 or abs(epoch)>10**29:
        raise ValueError('NONINTEGER_OR_OUT_OF_RANGE_EPOCH')
    quantities['n'] = epoch
    low, high, limit = (execute(candidate[name],quantities) for name in OUTPUTS[1:])
    if not 0 <= low <= high or limit<=0:
        raise ValueError('INVALID_UNCERTAINTY_INTERVAL')
    decision = 'WITHIN' if high<=limit else 'EXCEEDS' if low>limit else 'COVARIANCE_SENSITIVE'
    return {'epoch':int(epoch),'sigma_s':[floor(low),ceil(high)],'witness':witness,'decision':decision}


def development(path, arm, feedback=False):
    rows = read_json(path)
    if arm=='typed':
        shape = {'fields':MEANINGS, 'container':'ephemeris'}
    else:
        shape = {'order':list(FIELDS), 'descriptions':[[key,*MEANINGS[key]] for key in FIELDS], 'container':'row'}
    examples = [{'input':item['input'] if arm=='typed' else positional(item['input']), 'expected':item['expected']}
                for item in rows]
    return ((HARNESS if arm=='harness' else '')+TASK+'\n'+(FEEDBACK if feedback else '')
            +canonical({'format':shape,'examples':examples}).decode())


class ObservedConstructor(Constructor):
    def __init__(self, config, model):
        super().__init__(config,model,prepare_schema(SCHEMA))
        if self.provider.remote or self.provider.kind!='openai' or not self.provider.models[model].json_schema:
            raise ValueError('LOCAL_SCHEMA_MODEL_REQUIRED')
        sender = self.runtime.sender
        self.observation = None

        def observe(*args, **kwargs):
            response = sender(*args,**kwargs)
            self.observation = completion(response)
            return response

        self.runtime.sender = observe


def completion(response):
    if type(response) is not dict:
        return None
    choices = response.get('choices')
    if not isinstance(choices,list) or not choices or type(choices[0]) is not dict:
        return None
    selected = choices[0]
    reported = response.get('usage')
    usage = reported if type(reported) is dict else {}
    tokens = usage.get('completion_tokens_details')
    details = tokens if type(tokens) is dict else {}
    message = selected.get('message')
    content = message if type(message) is dict else {}
    finish = selected.get('finish_reason')
    states = ('stop','length','content_filter','tool_calls')
    result = {'finish':finish if finish in states else 'unknown'}
    for label,value in (('prompt_tokens',usage.get('prompt_tokens')),('completion_tokens',usage.get('completion_tokens')),
                        ('reasoning_tokens',details.get('reasoning_tokens'))):
        result[label] = value if type(value) is int and 0<=value<=10**7 else None
    for label in ('content','reasoning_content'):
        result[label+'_bytes'] = len(content[label].encode()) if type(content.get(label)) is str else None
    return result


def construct(args):
    model=ObservedConstructor(args.config,args.model)
    prompt=development(args.development,args.arm,args.feedback)
    args.workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    with lock(args.workspace):
        kind='liberation-feedback-' if args.feedback else 'liberation-'
        bound={'kind':kind+args.arm,'request_tokens':args.tokens,'prompt_sha256':digest(prompt),
               'schema_sha256':digest(prepare_schema(SCHEMA))}
        run=ResearchRun(args.workspace/'run.json',model,args.tokens,bound)
        if run.state['status']!='RUNNING':
            return run.state
        if run.state['events']:
            prior=run.state['events'][-1]
            return run.finish('SEALED',prior['candidate']) if prior['status']=='SEALED' else run.finish('ABSTAIN')
        if time()>=args.until:
            raise ValueError('LEASE_EXPIRED')
        response,event=run.invoke(prompt,{})
        event['response_shape']=model.observation
        if response is not None:
            event['draft']=response
        if model.observation and model.observation['finish']=='length':
            event.update(status='REFUSED',reason='PROVIDER_OUTPUT_LIMIT')
            run.settle(event)
            return run.finish('ABSTAIN')
        try:
            programs(response)
        except (SyntaxError,ValueError,TypeError) as error:
            event.update(status='REFUSED',reason=event.get('reason','ARTIFACT_CONTRACT'),diagnosis=str(error)[:160])
            run.settle(event)
            return run.finish('ABSTAIN')
        event.update(status='SEALED',candidate=response)
        run.settle(event)
        return run.finish('SEALED',response)


def score(source, cases):
    artifact=programs(source) if source is not None else None
    verdicts=Counter()
    issues=[]
    unsupported=0
    relevant=0
    for item in cases:
        case,result=item['input'],item['expected']
        if calculate(case)!=result or verified(case)!=result:
            raise ValueError('REFERENCE_DISAGREEMENT')
        relevant += not result['decision'].startswith('ABSTAIN')
        actual=None
        if artifact is None:
            category='NO_CANDIDATE'
        else:
            try:
                actual=project(artifact,case)
                category='ACCEPT' if actual==result else 'WRONG_RESULT'
            except (ArithmeticError,ValueError):
                category='EXECUTION_REFUSAL'
        verdicts[category]+=1
        if category!='ACCEPT':
            issues.append({'witness':case['witness'],'category':category})
            unsupported += actual is not None and actual['decision']=='WITHIN'
    return {'cases':len(cases),'nonabstaining_reference':relevant,'outcomes':dict(verdicts),
            'unsupported_within':unsupported,'negative':issues}


def emit(path,value):
    with path.open('xb') as stream:
        stream.write(canonical(value)+b'\n')


def packet(args):
    prompt=development(args.development,args.arm)
    body={'schema':'frontier/liberation-packet-v1','prompt':prompt,
          'development_sha256':sha256(args.development.read_bytes()).hexdigest(),
          'authority':'Public research. Return the four expressions and disclose the actual author or account pathway.'}
    emit(args.output,{**body,'packet_sha256':fingerprint(body)})


def receive(args):
    document=read_json(args.packet)
    token=document.pop('packet_sha256',None)
    response=read_json(args.response)
    if (document.get('schema')!='frontier/liberation-packet-v1' or token!=fingerprint(document)
            or set(response)!={'packet_sha256','author','programs'} or response['packet_sha256']!=token
            or type(response['author']) is not str or not 0<len(response['author'])<=140):
        raise ValueError('HANDOFF_BINDING')
    programs(response['programs'])
    emit(args.output,{'status':'SEALED','result':response['programs'],
         'binding':{'packet_sha256':token,'author':response['author'],'kind':'operator-assisted',
                    'response_sha256':sha256(args.response.read_bytes()).hexdigest()}})


def evaluate(args):
    receipt=read_json(args.candidate)
    result=receipt['result'] if receipt.get('status')=='SEALED' else None
    return {'candidate_sha256':sha256(args.candidate.read_bytes()).hexdigest(),
            'confirmation_sha256':sha256(args.confirmation.read_bytes()).hexdigest(),
            **score(result,read_json(args.confirmation))}


def select(args):
    with args.brief.open('rb') as stream:
        brief_bytes=stream.read(6001)
    if not 0<len(brief_bytes)<=6000:
        raise ValueError('OBSERVED_BRIEF_LENGTH')
    prompt=('Choose one high-value investigation for MONTREAL.AI using the public results below. '
            'Identify a genuinely missing fact and a decisive independent test that can change an actual research decision. '
            'You may choose a different scientific domain. Keep each answer short and finish every sentence. '
            'Use the specified JSON fields. Do not claim a new empirical outcome.\n'+brief_bytes.decode())
    return step(args.workspace,args.config,args.model,INVESTIGATION,prompt,'liberation-next',
                args.tokens,attempts=1,deadline=args.until)


def interrupt(_signum,_frame):
    raise KeyboardInterrupt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('construct')
    pack=sub.add_parser('packet')
    for command in (build,pack):
        command.add_argument('--development',type=Path,required=True)
        command.add_argument('--arm',choices=ARMS,required=True)
    for name in ('config','workspace'):
        build.add_argument('--'+name,type=Path,required=True)
    build.add_argument('--model',required=True)
    build.add_argument('--tokens',type=int,required=True)
    build.add_argument('--until',type=int,required=True)
    build.add_argument('--feedback',action='store_true')
    build.set_defaults(action=construct)
    pack.add_argument('--output',type=Path,required=True)
    pack.set_defaults(action=packet)
    importer=sub.add_parser('import')
    for name in ('packet','response','output'):
        importer.add_argument('--'+name,type=Path,required=True)
    importer.set_defaults(action=receive)
    evaluator=sub.add_parser('evaluate')
    for name in ('candidate','confirmation'):
        evaluator.add_argument('--'+name,type=Path,required=True)
    evaluator.set_defaults(action=evaluate)
    proposal=sub.add_parser('select')
    for name in ('brief','config','workspace'):
        proposal.add_argument('--'+name,type=Path,required=True)
    proposal.add_argument('--model',required=True)
    proposal.add_argument('--tokens',type=int,required=True)
    proposal.add_argument('--until',type=int,required=True)
    proposal.set_defaults(action=select)
    args=parser.parse_args()
    signal.signal(signal.SIGTERM,interrupt)
    try:
        result=args.action(args)
    except KeyboardInterrupt:
        parser.exit(130,'Paused. Reopen the same bounded workspace and configuration.\n')
    if result is not None:
        print(canonical(result).decode())


if __name__=='__main__':
    main()
