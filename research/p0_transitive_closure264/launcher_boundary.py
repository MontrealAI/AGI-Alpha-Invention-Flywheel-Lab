"""P0-264 supplementary development experiment: nested interpreter policy.

Fixed cases: clean ordinary child, isolated parent, ordinary nested child with
synthetic user-site hook, isolated nested child with same hook. Only local
temporary directories; no canonical runtime, keys, account or network.
Acceptance: clean child does not observe hook; parent does not observe hook;
ordinary child observes hook; isolated child does not; flags match.
This demonstrates a Python startup property, not a native audit failure.
"""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

PARENT = r'''
import json, os, subprocess, sys
p=json.load(sys.stdin)
root=p["root"]
env={**os.environ, "PYTHONPATH":root, "PYTHONDONTWRITEBYTECODE":"1"}
code="import json,sys;print(json.dumps([sys.flags.isolated,sys.flags.no_site,'p0264_synthetic_hook' in sys.modules]))"
def run(flags):
    done=subprocess.run([sys.executable,*flags,"-c",code],cwd=root,env=env,
                        text=True,capture_output=True,timeout=60,check=True)
    return json.loads(done.stdout.splitlines()[-1])
print(json.dumps({"parent":[sys.flags.isolated,sys.flags.no_site,
                            "p0264_synthetic_hook" in sys.modules],
                  "ordinary":run([]),"isolated":run(["-I","-S","-B"])}))
'''

def main():
    start=time.monotonic()
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with tempfile.TemporaryDirectory(prefix="p0264-policy-") as directory:
        base=Path(directory)
        home=base/"home";home.mkdir()
        root=base/"root";root.mkdir()
        env={"HOME":str(home),"PATH":os.defpath,"LANG":"C.UTF-8",
             "PYTHONDONTWRITEBYTECODE":"1"}
        exe=sys.executable
        def parent():
            done=subprocess.run([exe,"-I","-S","-B","-c",PARENT],
                input=json.dumps({"root":str(root)}),cwd=root,env=env,
                text=True,capture_output=True,timeout=60,check=True)
            return json.loads(done.stdout.splitlines()[-1])
        clean=parent()
        site=subprocess.check_output([exe,"-I","-S","-B","-c",
            "import site;print(site.getusersitepackages())"],
            cwd=root,env=env,text=True,timeout=60).strip()
        user=Path(site)
        if not user.is_absolute() or not user.is_relative_to(home):
            raise ValueError("SYNTHETIC_SITE_OUTSIDE_TEMP_HOME")
        user.mkdir(parents=True)
        (user/"p0264_synthetic_hook.py").write_text("MARKER = True\n")
        (user/"usercustomize.py").write_text("import p0264_synthetic_hook\n")
        with_hook=parent()
        checks={
            "clean_ordinary":clean["ordinary"]==[0,0,False],
            "isolated_parent":with_hook["parent"]==[1,1,False],
            "ordinary_nested_hook":with_hook["ordinary"]==[0,0,True],
            "isolated_nested_no_hook":with_hook["isolated"]==[1,1,False],
        }
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result={"checks":checks,"accepted":all(checks.values()),"clean":clean,
            "with_hook":with_hook,"python":sys.version.split()[0],
            "waited_child_cpu_seconds":after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
            "wall_seconds":time.monotonic()-start,"actual_billing_usd":None,
            "scope":"synthetic interpreter startup only"}
    print(json.dumps(result,sort_keys=True))
    return 0 if result["accepted"] else 1

if __name__=="__main__":
    raise SystemExit(main())
