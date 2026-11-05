"""Add new service dispatch only in a new isolated prospective test runtime."""
from pathlib import Path
import shutil
from enterprise078.runtime import materialize

SCHEMA='enterprise078/sql-csv-native/v1'


def stage(root,destination):
    root=Path(root);out=materialize(root,destination)
    for folder in ('transactional_native','transactional_data','transactional_admission'):
        for p in (root/'enterprise078'/folder).glob('*.py'):
            target=out/'enterprise078'/folder/p.name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
    p=out/'commercial/ledger.py';s=p.read_text()
    # Duplicate only the existing domain dispatch blocks for a DISTINCT schema.
    # Original branches and all financial operations remain intact.
    lines=s.splitlines(True);result=[];i=0;count=0
    while i<len(lines):
        line=lines[i]
        if "if " in line and "== 'enterprise078/native-services/v1':" in line:
            indent=len(line)-len(line.lstrip());block=[line];j=i+1
            while j<len(lines) and (not lines[j].strip() or len(lines[j])-len(lines[j].lstrip())>indent):
                block.append(lines[j]);j+=1
            clone=''.join(block).replace('enterprise078/native-services/v1',SCHEMA).replace('from enterprise078.service import','from enterprise078.transactional_native.service import')
            result.append(clone)
            # A dispatch chain's original if becomes elif after its new branch.
            result.append(line.replace('if ','elif ',1))
            result.extend(lines[i+1:j]);i=j;count+=1
        else:result.append(line);i+=1
    if count!=5:raise ValueError('EXACT_FIVE_NATIVE_SERVICE_DISPATCHES_REQUIRED')
    s=''.join(result).replace("'enterprise078/native-services/v1'}", "'enterprise078/native-services/v1', '"+SCHEMA+"'}")
    p.write_text(s)
    p=out/'connected_enterprise/finance.py';s=p.read_text()
    marker="    if schema == 'enterprise078/native-services/v1':"
    assert s.count(marker)==1
    s=s.replace(marker,"    if schema == '"+SCHEMA+"':\n        from enterprise078.transactional_native.service import source_paths\n        return tuple(dict.fromkeys(SOURCE_PATHS + tuple(source_paths(Path(__file__).resolve().parents[1]))))\n"+marker)
    p.write_text(s)
    return out
