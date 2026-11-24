"""Construct and challenge an isolated monitoring policy using HARNESS."""

import argparse
from hashlib import sha256
from pathlib import Path
import sys
from time import perf_counter_ns
from uuid import uuid4

from bridge.adapters import BridgeError
from bridge.instruments import strict_portable_json
from inventor import Model, Run, compact, load, record
from study import lock
from learning import clock, conventional, eligible, examples, quantile
from pages import EVENTS, digest
from provider import request_plan
from wasm_policy import INPUTS, OPS, Policy, Refused, expression_wat, lower

ARMS = ('original','ordinary','augmented','withdrawn')
WAT_OUTPUT = {'type':'object','properties':{'hypothesis':{'type':'string','maxLength':120},
                                           'wat':{'type':'string','maxLength':1200}},
              'required':['hypothesis','wat'],'additionalProperties':False}
STACK_OUTPUT = {'type':'object','properties':{'hypothesis':{'type':'string','maxLength':90},
    'program':{'type':'array','minItems':1,'maxItems':24,'items':{'anyOf':[
        {'type':'integer','minimum':-4096,'maximum':4096},{'enum':[*INPUTS,*OPS]}]}}},
    'required':['hypothesis','program'],'additionalProperties':False}
EXPRESSION_OUTPUT = {'type':'object','properties':{'hypothesis':{'type':'string','maxLength':90},
                                                  'expression':{'type':'string','maxLength':160}},
                     'required':['hypothesis','expression'],'additionalProperties':False}


class ResearchModel(Model):
    def __init__(self,args):
        super().__init__(args)
        self.output={'wat':WAT_OUTPUT,'stack':STACK_OUTPUT,'expression':EXPRESSION_OUTPUT}[args.representation]

    def call(self, prompt, limit):
        if not self.provider.models[self.name].json_schema:
            return super().call(prompt,limit)
        plan=request_plan(self.runtime,self.provider,self.name,prompt,limit,False)
        canonical_plan={**plan,'output_contract_sha256':digest(self.output)}
        canonical_plan['approval_sha256']=digest(canonical_plan)
        request={'provider':self.provider.id,'model':self.name,'prompt':prompt,'max_output_tokens':limit,
                 'run_id':uuid4().hex,'json_schema':self.output}
        return self.runtime.generate(request,expected_provider=self.provider),canonical_plan


class ResearchRun(Run):
    """Keep the existing checkpoint accounting with a larger WAT request allowance."""

    def invoke(self, prompt, details):
        limit=min(self.remaining,self.state['binding']['request_tokens'])
        receipt={**details,'prompt_sha256':sha256(prompt.encode()).hexdigest(),'reserved_output':limit}
        self.state['pending']=receipt
        self.save()
        start=perf_counter_ns()
        response=None
        try:
            reply,plan=self.model.call(prompt,limit)
            used=reply['usage']['output_tokens']
            if used is not None and not 0<used<=limit:
                raise ValueError('OUTPUT_BUDGET')
            receipt.update(usage=reply['usage'],plan_sha256=plan['approval_sha256'],reported_model=reply['reported_model'],
                           response_sha256=sha256(reply['text'].encode()).hexdigest(),
                           used_output=limit if used is None else used,status='RECEIVED')
            response=strict_portable_json(reply['text'])
        except (BridgeError,ValueError,RecursionError) as error:
            receipt.update(status='REFUSED',reason=error.code if isinstance(error,BridgeError) else 'RESPONSE',
                           used_output=receipt.get('used_output',limit))
        finally:
            receipt['wall_ns']=perf_counter_ns()-start
        return response,receipt


def machine(candidate):
    wat=candidate['wat']
    if ('program' in candidate and lower(candidate['program'])!=wat or
            'expression' in candidate and expression_wat(candidate['expression'])!=wat):
        raise Refused('ARTIFACT_COMPILATION_DRIFT')
    return Policy(wat)


def policy_monitor(candidate, cases):
    compiled = machine(candidate)
    return clock(cases,lambda elapsed, median, p80, p95, reads, _:compiled(elapsed,median,p80,p95,reads))


def proof_program(reply, representation):
    if representation=='wat':
        return record(reply,{'hypothesis':650,'wat':4096})
    if representation=='expression':
        candidate=record(reply,{'hypothesis':90,'expression':160})
        return {**candidate,'wat':expression_wat(candidate['expression'])}
    if type(reply) is not dict or set(reply)!={'hypothesis','program'}:
        raise Refused('PROGRAM_FIELDS')
    record({'hypothesis':reply['hypothesis']},{'hypothesis':90})
    return {**reply,'wat':lower(reply['program'])}


def report_metrics(result):
    return {key:result[key] for key in ('cases','reads','p95_delay','max_delay')}


def development_items(cases):
    controls = conventional(cases)
    reference = controls['empirical-survival']['details']
    result = []
    for row, observed in zip(cases,reference):
        typical = round(row['base'])
        p80, p95 = (quantile(row['times'],p) for p in (80,95))
        actual = row['actual']
        family = 'early' if actual<typical else 'late' if actual>p80 else 'near'
        result.append({'id':row['id'],'family':family,'typical':typical,'p80':p80,'p95':p95,
                       'completed_second':actual,'conventional_reads':observed['reads'],
                       'conventional_delay':observed['delay']})
    return result, {key:report_metrics(row) for key,row in controls.items()}


def coverage(details):
    order = sorted(details,key=lambda r:(r['conventional_delay'],r['conventional_reads']),reverse=True)
    picked = [next(row for row in order if row['family']==name) for name in ('early','near','late')
              if any(row['family']==name for row in order)]
    return picked+[row for row in order if row not in picked]


def ranking(policy, rows):
    def score(row):
        group = sum(r['family']==row['family'] for r in rows)
        late = int(row['family']=='late')
        error = abs(row['completed_second']-row['typical'])
        return policy(row['conventional_delay'],row['conventional_reads'],error,late,group)
    return sorted(rows,key=score,reverse=True)


def previews(rows, arm, prior):
    ordinary = coverage(rows)
    chosen = ordinary
    measurement = {'method_executed':False,'scope':'development-only'}
    if arm == 'ordinary':
        order = prior['fixed_family_order']
        choices = [next(row for row in ordinary if row['family']==family) for family in order
                   if any(row['family']==family for row in ordinary)]
        chosen = choices+[row for row in ordinary if row not in choices]
    if arm == 'augmented':
        try:
            chosen = ranking(machine(prior['method']),ordinary)
            measurement['method_executed'] = True
        except Refused as error:
            measurement['method_error'] = str(error)
    measurement['coverage_ids'] = [row['id'] for row in ordinary[:4]]
    measurement['selected_ids'] = [row['id'] for row in chosen[:4]]
    measurement['changed_selection'] = set(measurement['selected_ids']) != set(measurement['coverage_ids'])
    return chosen[:4], measurement


def determine(run, cases, arm, prior, mode):
    if run.state['status'] != 'RUNNING':
        return run.state
    rows, incumbent = development_items(cases)
    selected, selection = previews(rows,arm,prior)
    previous = [e for e in run.state['events'] if 'candidate' in e]
    used = sum(e['status']!='INTERRUPTED' for e in run.state['events'])
    maximum_attempts = run.state['binding']['attempts']
    representation = run.state['binding']['representation']
    if previous and previous[-1]['status']=='ADVANCE':
        return run.finish('SEALED',previous[-1]['candidate'])
    while run.remaining >= 96 and used < maximum_attempts:
        previous_trial = run.state['events'][-1] if run.state['events'] else {}
        if mode == 'learn':
            task = ('Invent a reusable rule for ranking development counterexamples that will help a monitoring tool constructor. '
                    'Inputs are conventional detection delay, conventional reads, absolute error vs its median, late-family flag, '
                    'and count of this family. Return a signed integer priority, higher first. Compare simple alternative rules.')
        else:
            task = ('Invent a monitoring program. Inputs are elapsed seconds, prior median seconds, prior p80 seconds, prior p95 seconds, '
                    'and number of status reads already made. Return seconds to wait until the next read, integer 5 through 60. '
                    'Use only these five inputs. Aim for fewer reads with p95 detection delay <=20 seconds and maximum <=60. '
                    'Think of alternative mechanisms, then implement one. The observed outcomes below are development diagnostics only.')
        formats = {
            'stack':(' Return JSON with hypothesis and program, a postfix list. The inputs in order are a,b,c,d,e. '
                     'Use integers, input names, or '+','.join(OPS)+'. For choose: true value, false value, condition. '
                     'Leave exactly one value. Example [2,3,"+"] returns 5.'),
            'expression':(' Return JSON with hypothesis and expression, a short Python-style integer expression. '
                          'The five inputs in order are a,b,c,d,e. Only integers, variables, +, -, *, comparisons, '
                          'and conditional expressions are supported. Use x if condition else y. No calls or imports.'),
            'wat':(' Return JSON with hypothesis and wat. wat is a complete WebAssembly text module with no imports '
                   'and one exported function named choose, taking five i32 inputs and returning one i32.'),
        }
        format_rule=formats[representation]
        prompt = (task+format_rule+'\n'+compact({
                     'development':selected,'baseline':incumbent,'prior':prior,
                     'previous_failure':{key:previous_trial[key] for key in
                                         ('status','diagnosis','diagnostic_excerpt','score') if key in previous_trial},
                  }))
        reply, event = run.invoke(prompt,{'selection':selection})
        used += 1
        if reply is not None:
            event['draft']=reply
        try:
            candidate = proof_program(reply,representation)
            event['proposed']=candidate
            if mode == 'learn':
                ranked = ranking(machine(candidate),rows)
                candidate = {'method':candidate,'fixed_family_order':list(dict.fromkeys(r['family'] for r in ranked)),
                             'parent_sha256':digest(prior)}
                event.update(status='ADVANCE',candidate=candidate)
            else:
                score = report_metrics(policy_monitor(candidate,cases))
                best = min(row['reads'] for row in incumbent.values() if eligible(row))
                advance = eligible(score) and score['reads']*10 <= best*9
                event.update(status='ADVANCE' if advance else 'REVISE',candidate=candidate,score=score)
                previous.append(event)
        except ValueError as error:
            event.update(status='REFUSED',diagnosis=str(error))
            if isinstance(error,Refused) and error.__cause__:
                event['diagnostic_excerpt']=str(error.__cause__)[:240]
        run.settle(event)
        if event['status']=='ADVANCE':
            return run.finish('SEALED',event['candidate'])
    if previous:
        best = min(previous,key=lambda x:(not eligible(x['score']),x['score']['p95_delay'],x['score']['reads']))
        return run.finish('DEVELOPMENT_INCOMPLETE',best['candidate'])
    return run.finish('ABSTAIN')


def main(args):
    if not 96<=args.request_tokens<=512 or not args.request_tokens<=args.budget<=1024:
        raise ValueError('RESEARCH_BUDGET')
    history, batch = load(args.history),load(args.development)
    cases = [row for row in examples(batch,history) if row['event']==args.event]
    if len(cases)<5:
        raise ValueError('RESEARCH_DEVELOPMENT_CASES')
    prior = load(args.prior) if args.prior else None
    if (args.mode=='learn' or args.arm!='original') and prior is None:
        raise ValueError('RESEARCH_PRIOR')
    args.workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    binding = {'kind':'adaptive-'+args.mode,'event':args.event,'arm':args.arm,'attempts':args.attempts,
               'request_tokens':args.request_tokens,'representation':args.representation,
               'history_sha256':digest(history),'development_sha256':digest(batch),
               'prior_sha256':digest(prior) if prior else None}
    with lock(args.workspace):
        run = ResearchRun(args.workspace/'run.json',ResearchModel(args),args.budget,binding)
        return determine(run,cases,args.arm,prior,args.mode)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('construct','learn'))
    parser.add_argument('--event',choices=EVENTS,required=True)
    parser.add_argument('--arm',choices=ARMS,default='original')
    for name in ('history','development','config','workspace'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--prior',type=Path)
    parser.add_argument('--model',required=True)
    parser.add_argument('--provider',required=True)
    parser.add_argument('--budget',type=int,required=True)
    parser.add_argument('--request-tokens',choices=(256,512),type=int,default=256)
    parser.add_argument('--representation',choices=('expression','stack','wat'),default='expression')
    parser.add_argument('--attempts',choices=(1,2),type=int,default=1)
    try:
        print(compact(main(parser.parse_args())))
    except (BridgeError,ValueError,OSError,TypeError,KeyError,RecursionError) as error:
        print('Research stopped: '+str(error),file=sys.stderr)
        sys.exit(2)
