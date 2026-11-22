"""Explicit opt-in Codex/ChatGPT adapter. No API keys or paid API fallback."""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .checker import bundle, check, Rejected


def repair(source, contract, output, model=None, attempts=3, request_seconds=600):
    if type(attempts) is not int or not 1 <= attempts <= 20:
        raise Rejected('attempts must be 1..20 for this registered run')
    if request_seconds <= 0: raise Rejected('positive request deadline required')
    # Validate both original program and contract before sharing with provider.
    initial, _ = check(source, contract)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'schema':1, 'status':'BLOCKED', 'provider':'codex-chatgpt', 'requested_model':model or 'configured-default',
               'attempts':[], 'billing_usd':None, 'billing_note':'ChatGPT-plan access subject to account limits; resource cost not measured',
               'initial_status':initial['status'], 'accepted_bundle':None}
    def save(): (out/'repair.json').write_text(json.dumps(receipt, indent=2)+'\n')
    if not shutil.which('codex'):
        receipt['reason']='CODEX_UNAVAILABLE'; save(); return receipt
    try:
        auth = subprocess.run(['codex','login','status'], capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        receipt['reason']='CODEX_LOGIN_STATUS_UNAVAILABLE'; save(); return receipt
    if auth.returncode != 0 or 'ChatGPT' not in auth.stdout+auth.stderr:
        receipt['reason']='CHATGPT_LOGIN_REQUIRED_NO_API_FALLBACK'; save(); return receipt
    feedback = initial
    for index in range(attempts):
        prompt = ('Repair this pure Python integer function to exactly satisfy the frozen contract. '
                  'Return only the JSON object {"source": "..."}. Do not use tools, read other files or change the contract. '
                  'Allowed grammar: one function with positional args, one return of integer literals/names, + - *, '
                  '// or % by positive literal, integer comparisons, and/or within conditions, conditional expression. '
                  'No calls/imports/loops/defaults/decorators/annotations.\n'
                  + json.dumps({'contract':contract,'original_source':source,'feedback':feedback}))
        with tempfile.TemporaryDirectory(prefix='proof-omega-') as tmp:
            reply = Path(tmp)/'reply.txt'
            schema = Path(tmp)/'schema.json'
            schema.write_text(json.dumps({'type':'object','properties':{'source':{'type':'string'}},'required':['source'],'additionalProperties':False}))
            cmd = ['codex','exec','--sandbox','read-only','--skip-git-repo-check','--ephemeral','-C',tmp,
                   '--output-schema',str(schema),'--output-last-message',str(reply)]
            if model: cmd.extend(['--model',model])
            cmd.append('-')
            start = time.monotonic()
            try:
                run = subprocess.run(cmd,input=prompt,text=True,capture_output=True,timeout=request_seconds)
                event = {'attempt':index+1,'wall_seconds':time.monotonic()-start,'provider_exit':run.returncode}
                if run.returncode:
                    event['status']='PROVIDER_ERROR'; receipt['attempts'].append(event)
                    receipt['reason']='CODEX_EXECUTION_FAILED'; save(); return receipt
                if not reply.exists() or reply.stat().st_size > 65536:
                    raise Rejected('missing/oversized response')
                proposed = json.loads(reply.read_text())
                if not isinstance(proposed,dict) or set(proposed) != {'source'} or not isinstance(proposed['source'],str):
                    raise Rejected('invalid response shape')
                feedback,_ = check(proposed['source'],contract)
                event['status']=feedback['status']; receipt['attempts'].append(event)
                if feedback['status']=='PROVED_SCOPED':
                    final = bundle(proposed['source'],contract,out/'candidate-bundle')
                    receipt['status']=final['status']
                    if final['status']=='PROVED_SCOPED':
                        receipt['accepted_bundle']='candidate-bundle'
                    else:
                        receipt['reason']='FINAL_RECHECK_NOT_PROVED'
                    save(); return receipt
            except subprocess.TimeoutExpired:
                receipt['attempts'].append({'attempt':index+1,'status':'PROVIDER_TIMEOUT','wall_seconds':time.monotonic()-start})
                receipt['reason']='REQUEST_DEADLINE'; save(); return receipt
            except (ValueError, OSError, Rejected) as exc:
                feedback={'status':'REJECTED','reason':str(exc)}
                receipt['attempts'].append({'attempt':index+1,'status':'REJECTED','wall_seconds':time.monotonic()-start})
    receipt['status']='NOT_PROVED'; receipt['reason']='ATTEMPTS_EXHAUSTED'; save(); return receipt
