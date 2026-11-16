#!/usr/bin/env python3
"""Pinned local CPU inference inside the complete ALPHA operating loop.

No cloud credentials, paid model API or real financial transaction. Uses the same
upstream pins as the existing HARNESS hosted qualification. Weights stay transient.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from connected_enterprise.alpha_economic.agents import HarnessAgent
from connected_enterprise.alpha_economic.commerce import SimulatedBuyer
from connected_enterprise.alpha_economic.core import digest,sign,save
from connected_enterprise.alpha_economic.demo import example
from connected_enterprise.alpha_economic.runtime import Engine,default_policy

BINARY=('https://github.com/ggml-org/llama.cpp/releases/download/b12242/llama-b12242-bin-ubuntu-x64.tar.gz','909eef25cd53e6601c8a07c866d8dbb2983e74177088d55182137a8fb8255d62',23158635)
MODEL=('https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/resolve/ae44f08e1392f39c0e474af10c3ff8355c8b6688/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf','2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e',2497280736)
LICENSE='https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/cdbee75f17c01a7cc42f958dc650907174af0554/LICENSE'


def download(spec,target):
    url,expected,size=spec;h=hashlib.sha256();total=0
    with urllib.request.urlopen(url,timeout=120) as response,open(target,'wb') as f:
        for data in iter(lambda:response.read(4*1024*1024),b''):
            total+=len(data)
            if total>size:raise ValueError('PINNED_DOWNLOAD_SIZE_EXCEEDED')
            f.write(data);h.update(data)
    if total!=size or h.hexdigest()!=expected:raise ValueError('PINNED_DOWNLOAD_IDENTITY_MISMATCH')
    return {'url':url,'sha256':expected,'bytes':total}


def run(work,public):
    work=Path(work).resolve();public=Path(public).resolve()
    work.mkdir(parents=True,exist_ok=False);public.mkdir(parents=True,exist_ok=False)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    result={'source_revision':revision,'qualification':'RUNNING','actual_model_inference':False,
            'real_customers_observed':0,'actual_collections':0,'paid_model_api_calls':0,
            'complete_actual_cost_profit':None,'cost_scope':'LOCAL_CPU_BILLING_UNKNOWN_MODELED_ECONOMIC_ENVELOPE_ONLY',
            'model':'Qwen3-4B-Instruct-2507-Q4_K_M','accelerator':'CPU','inference_threads':2}
    save(public/'LOCAL-MODEL-RESULT.json',result)
    proc=None;engine=None;log=None
    try:
        result['binary_download']=download(BINARY,work/'runtime.tar.gz')
        result['model_download']=download(MODEL,work/'model.gguf')
        with urllib.request.urlopen(LICENSE,timeout=60) as response:license_bytes=response.read(100000)
        if b'Apache License' not in license_bytes:raise ValueError('MODEL_LICENSE_NOT_CONFIRMED')
        result['model_license_sha256']=hashlib.sha256(license_bytes).hexdigest()
        with tarfile.open(work/'runtime.tar.gz') as a:a.extractall(work/'runtime',filter='data')
        binary=list((work/'runtime').rglob('llama-server'))
        if len(binary)!=1:raise ValueError('EXACT_RUNTIME_BINARY_REQUIRED')
        binary=binary[0];result['server_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
        with socket.socket() as sock:sock.bind(('127.0.0.1',18768))
        env={k:os.environ[k] for k in ('PATH','HOME','LANG','LC_ALL','TMPDIR') if k in os.environ}
        env['LD_LIBRARY_PATH']=str(binary.parent);env['NO_PROXY']='127.0.0.1,localhost'
        log=open(work/'server.log','w')
        proc=subprocess.Popen([str(binary),'-m',str(work/'model.gguf'),'--alias','alpha-local','--host','127.0.0.1','--port','18768','-c','8192','-t','2','-ngl','0'],env=env,stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if proc.poll() is not None:raise RuntimeError('LOCAL_MODEL_SERVER_STOPPED')
            try:
                with urllib.request.urlopen('http://127.0.0.1:18768/health',timeout=2) as response:
                    if response.status==200:break
            except (OSError,TimeoutError):time.sleep(1)
        else:raise TimeoutError('LOCAL_MODEL_STARTUP_FAILED')
        cfg={'kind':'harness','max_output_tokens':768,'runtime':{'local_only':True,'allow_paid_requests':False,'timeout_seconds':600,'max_attempts':1,
            'providers':{'local':{'kind':'openai','base_url':'http://127.0.0.1:18768/v1','output_limit_field':'max_tokens',
            'models':{'alpha-local':{'input_per_million':0,'output_per_million':0,'json_mode':True,'max_output_tokens':768,'context_window':8192}}}}},
            'routes':{'construct':{'provider':'local','model':'alpha-local'}}}
        agent=HarnessAgent(cfg);keys={'buyer-demo':b'LOCAL-MODEL-QUALIFICATION-SYNTHETIC-BUYER-0123456789'}
        engine=Engine(work/'engine',default_policy(),agent,SimulatedBuyer(keys),keys)
        observations=[];original=agent.service.generate
        def observed(*args,**kwargs):
            start=time.monotonic()
            try:
                response=original(*args,**kwargs)
                observations.append({'completed':True,'wall_seconds':time.monotonic()-start,
                    'reported_model':response.get('reported_model'),'usage':response.get('usage'),'usage_class':response.get('usage_class'),
                    'output_text_sha256':hashlib.sha256(response['text'].encode()).hexdigest()})
                return response
            except Exception as exc:
                observations.append({'completed':False,'wall_seconds':time.monotonic()-start,'error_type':type(exc).__name__});raise
        agent.service.generate=observed
        c=example();job=engine.submit(sign({'kind':'request','buyer':c['buyer'],'expires_at':c['expires_at'],'contract':c},keys[c['buyer']]))
        report=engine.run(max_ticks=100,poll=.01)
        first=engine.state.get(job);result['observations']=observations
        result['actual_model_inference']=any(x.get('completed') for x in observations)
        result['model_response_selected']=first['data'].get('artifact',{}).get('provenance',{}).get('qualification')=='LIVE_RESPONSE_NOT_INDEPENDENT_VERIFICATION'
        result['first_job']=job;result['first_state']=first['state'];result['first_attempts']=engine.state.attempts(job)
        c2=example(2);job2=engine.submit(sign({'kind':'request','buyer':c2['buyer'],'expires_at':c2['expires_at'],'contract':c2},keys[c2['buyer']]))
        second_report=engine.run(max_ticks=100,poll=.01);second=engine.state.get(job2)
        result['successor_provenance']=second['data'].get('artifact',{}).get('provenance')
        result['successor_attempts']=len(engine.state.attempts(job2))
        result['native_audit']=second_report['native_audit'];result['native_summary']=second_report['native_summary']
        result['qualification']='PASS' if (result['actual_model_inference'] and result['model_response_selected'] and first['state']=='COMPLETE' and second['state']=='COMPLETE' and second_report['native_audit']['accepted']) else 'FAIL'
        result['control']='DECLARED_COMPETENT_ORDINARY_INSTRUMENT_ALSO_PASSES_NO_SUPERIORITY_CLAIM'
        if first['data'].get('artifact'):save(public/'MODEL-CONSTRUCTED-INSTRUMENT.json',first['data']['artifact'])
        # No keys, recovery authority, customer private data, weights or account DB published.
        save(public/'MODEL-ECONOMIC-RESULTS.json',second_report)
    except BaseException as exc:
        result['qualification']='FAIL';result['error_type']=type(exc).__name__;result['error']=str(exc)[:300]
    finally:
        if engine:engine.close()
        if proc:
            proc.terminate()
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        if log:log.close()
        result['server_stopped']=proc is None or proc.poll() is not None
        save(public/'LOCAL-MODEL-RESULT.json',result)
    print(json.dumps(result,indent=2))
    return 0 if result['qualification']=='PASS' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',required=True);p.add_argument('--public',required=True)
    a=p.parse_args();raise SystemExit(run(a.work,a.public))
