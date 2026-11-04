"""Fresh-directory actual construction or explicitly separate proof-only replay.

The default package is this source directory, including frozen model arrays.
Requires preinstalled NumPy/SciPy and a source-bound separately owned checker.
"""
import argparse,hashlib,json,os,pathlib,resource,shutil,subprocess,sys,time

ROOT=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def checked_copy(source,target,size=None,digest=None):
    source=pathlib.Path(source)
    if source.is_symlink() or not source.is_file():raise ValueError('regular input file required: '+str(source))
    if size is not None and source.stat().st_size!=size:raise ValueError('size changed: '+str(source))
    if digest is not None and sha(source)!=digest:raise ValueError('hash changed: '+str(source))
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
def limits(cpu):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+5))
        resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
        resource.setrlimit(resource.RLIMIT_FSIZE,(64<<20,64<<20))
    return apply
def run(command,folder,label,cpu,wall,network=False):
    environment={k:v for k,v in os.environ.items() if k in ['PATH','LANG','LC_ALL','SYSTEMROOT','LD_LIBRARY_PATH']}
    if network:
        # Trusted, fixed-URL data preparation only. Keep required proxy/TLS
        # configuration without printing values; numerical children omit it.
        for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy','SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE']:
            if key in os.environ:environment[key]=os.environ[key]
    environment.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0')
    with (folder/f'{label}.stdout.log').open('wb') as stdout,(folder/f'{label}.stderr.log').open('wb') as stderr:
        result=subprocess.run(command,cwd=folder,env=environment,stdout=stdout,stderr=stderr,timeout=wall,preexec_fn=limits(cpu),start_new_session=True)
    if result.returncode:raise RuntimeError(f'{label} exited {result.returncode}; logs retained')
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=pathlib.Path,default=ROOT)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--data',type=pathlib.Path)
    parser.add_argument('--reference',type=pathlib.Path)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--mode',choices=['construct','proof'],default='construct')
    parser.add_argument('--records',type=pathlib.Path)
    parser.add_argument('--verifier',type=pathlib.Path)
    args=parser.parse_args();package=args.package.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    receipt={'status':'STARTED','mode':'ACTUAL_CONSTRUCTION_AND_SEPARATE_CHECK' if args.mode=='construct' else 'PROOF_ONLY_NO_CONSTRUCTION','edition':'XCT008_RECOVERY_FULL120_R1','scope':'EXPOSED_DEVELOPMENT_NEW_RECOVERY_EDITION','source_sha256':sha(pathlib.Path(__file__)),'limits':{'address_space_bytes':2<<30,'constructor_cpu_soft_seconds':700,'constructor_cpu_hard_seconds':705,'checker_cpu_seconds':180,'threads':1},'network_phase':'Trusted fixed-URL preparation preserves required proxy/TLS configuration; numerical children use reduced environment. Local inputs plus --offline need no network.','limitations':['Owned numerical process limits, not arbitrary native sandbox qualification.','Any outer resource wrapper must allow child hard limit705CPU and2GiB; actual allocation still applies.','No protected confirmation, physical validation, purchase or commercial claim.']}
    write(output/'REPLAY_RECEIPT.json',receipt)
    start=time.monotonic();old=resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_text())
        for name,digest in manifest['package_files'].items():
            if sha(package/name)!=digest:raise ValueError('package source/model changed: '+name)
        verifier=args.verifier
        if verifier is None:verifier=package.parents[2]/'verification/xct008_recovery/check_recovery.py'
        verifier=verifier.resolve()
        if sha(verifier)!=manifest['verifier']['sha256']:raise ValueError('separate verifier source changed')
        stage=output/'work';stage.mkdir()
        for name in ['construct.py','exact_feasibility.py','acquire.py','calibrate.py','PROTOCOL.json','DATA_LICENSE.md','SOURCES.json','data/zenodo_record.json','data/example.m','model/CALIBRATION.json','model/reference.npy','model/eps.npy','model/objective.npy']:
            checked_copy(package/name,stage/name,digest=manifest['package_files'][name])
        checked_copy(verifier,stage/'separate_verifier.py',digest=manifest['verifier']['sha256'])
        raw={'Data82.mat':(args.data,8083003,'03a35c57ae52026f980ffcf540a4243a02f198b3fcdd8dff72cb251f70b067cc'),'GroundTruthReconstruction.mat':(args.reference,9671701,'88cc17c0b9706a9cf88f615e490d0254e59e89ee88740d293d06c16a1d6005bd')}
        for name,(local,size,digest) in raw.items():
            if local is not None:checked_copy(local,stage/'data'/name,size,digest)
            elif args.offline:raise ValueError('--offline requires both --data and --reference')
        run([sys.executable,str(stage/'acquire.py')],output,'acquisition',15,240,network=True)
        if args.mode=='construct':
            records=stage/'constructed'
            run([sys.executable,str(stage/'construct.py'),'--output',str(records)],output,'construction',700,800)
        else:
            if args.records is None:raise ValueError('proof mode requires --records')
            records=stage/'proof_records'
            for source in args.records.rglob('*'):
                if source.is_symlink():raise ValueError('symlink in proof records')
                if source.is_file() and source.stat().st_size>64<<20:raise ValueError('proof record exceeds64MiB')
            shutil.copytree(args.records,records,symlinks=False)
        check_output=output/'separate_check'
        run([sys.executable,str(stage/'separate_verifier.py'),'--base',str(stage),'--records',str(records),'--output',str(check_output)],output,'verification',180,300)
        report=json.loads((check_output/'REPORT.json').read_text())
        if report.get('artifact_integrity_verified') is not True:
            raise ValueError('separate checker did not verify artifact integrity')
        receipt.update(status='COMPLETED',separate_report_status=report.get('status',report.get('verdict','SEE_REPORT')),records=str(records.relative_to(output)),separate_report=str((check_output/'REPORT.json').relative_to(output)),verified_inputs={name:sha(stage/'data'/name) for name in raw},separate_verifier_sha256=sha(verifier))
    except BaseException as error:
        receipt.update(status='INTERRUPTED_OR_FAILED',error=repr(error))
        raise
    finally:
        usage=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['resources']={'child_cpu_seconds':usage.ru_utime+usage.ru_stime-old.ru_utime-old.ru_stime,'wall_seconds':time.monotonic()-start,'peak_child_rss_kib':usage.ru_maxrss}
        write(output/'REPLAY_RECEIPT.json',receipt)
    print(json.dumps(receipt))
if __name__=='__main__':main()
