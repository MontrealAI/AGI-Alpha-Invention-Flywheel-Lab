#!/usr/bin/env python3
"""Apply an exact, data-only source revision on the publication authoring branch.

The JSON contains UTF-8 character offsets, replacement strings, and before/after
SHA-256 identities. It is never evaluated as code. All changes are validated
before any source is replaced; actual revised source is committed for review.
This bootstrap is idempotent and cannot apply to an unexpected source version.
"""
from pathlib import Path, PurePosixPath
import hashlib,json

ROOT=Path(__file__).resolve().parents[2]
PREFIX=ROOT/'docs/successor-omega'
NEW={
 'qualification.py':'d1449e21cc23a4cd7de5a4404408eb7ff8008815ff5b9744f30fa2d5fae9fe1f',
 'uncertainty.py':'b35de474edebe1683dd235810d58aceff8fc7385e7bedcd3ccf1be973753a2af',
 'test_review.py':'5e87388d5578ccefac688fb9596e60625ed108390ae0c6166f1d90cfd3697bdc',
 'test_uncertainty.py':'713903182e54015a1fe755561dd95c034c268781e7e8a3bd232484adf180ae42',
 'sections/review.tex':'5c86062badac11c3e1dd11570a16b32445f93583700ff25ceb53ab5a5d5b86ed',
 'sections/thesis.tex':'31e1a293a5efd6d5f71f9aac67c5caef5fc49d024b06380b11a93901bbce71ee',
 'REVIEW_PROTOCOL.md':'85d025690859c60b0c32711a00a2fdaff5bab9bb1b4daa2112d0a0c36f1f7aac',
 'REVIEW.md':'58ab8140b863a9027a6c0c1734c169384855e41041a077aabbc7b787ffb39d5a',
}
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    document=json.loads(Path(__file__).with_name('successor-review-edits.json').read_text())
    if document.get('schema')!=1 or len(document['files'])!=12:
        raise ValueError('Unexpected source-revision schema or file count')
    for name,expected in NEW.items():
        if sha((PREFIX/name).read_bytes())!=expected:
            raise ValueError('New source differs from reviewed input: '+name)
    pending=[];seen=set()
    for entry in document['files']:
        path=PurePosixPath(entry['path'])
        if (path.is_absolute() or '..' in path.parts or path.parts[:2]!=('docs','successor-omega')
                or str(path) in seen):raise ValueError('Unsafe or repeated source path')
        seen.add(str(path));target=ROOT/str(path)
        if not target.is_file() or target.resolve()!=target or target.is_symlink():
            raise ValueError('Source must be an existing ordinary file')
        original=target.read_bytes()
        if sha(original)==entry['after']:continue
        if sha(original)!=entry['before']:
            raise ValueError('Refusing unexpected source version: '+str(path))
        text=original.decode('utf-8');last=0
        for start,end,replacement in entry['edits']:
            if not (type(start) is int and type(end) is int and last<=start<=end<=len(text)
                    and type(replacement) is str):raise ValueError('Invalid edit interval')
            last=end
        for start,end,replacement in reversed(entry['edits']):
            text=text[:start]+replacement+text[end:]
        encoded=text.encode('utf-8')
        if sha(encoded)!=entry['after']:
            raise ValueError('Result differs from reviewed source: '+str(path))
        pending.append((target,encoded))
    for target,data in pending:target.write_bytes(data)
    print(f'Validated {len(NEW)} new files and 12 source revisions; applied {len(pending)} changes.')

if __name__=='__main__':main()
