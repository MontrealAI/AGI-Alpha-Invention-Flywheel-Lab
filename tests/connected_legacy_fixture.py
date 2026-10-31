import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def materialize(root, commit, destination):
    source=Path(root)/'historical/successor022';index=json.loads((source/'MANIFEST.json').read_text())
    record=index['versions'][commit];raw=(source/record['archive']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['sha256'] or len(raw)>2_000_000:
        raise ValueError('PINNED_LEGACY_FIXTURE_ARCHIVE_CHANGED')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(16_000_001)
    if len(decoded)!=record['decoded_tar_bytes'] or len(decoded)>16_000_000:
        raise ValueError('BOUNDED_PINNED_LEGACY_FIXTURE_REQUIRED')
    seen={};destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(decoded)) as archive:
        for item in archive.getmembers():
            relative=Path(item.name)
            if not item.isfile() or relative.is_absolute() or '..' in relative.parts or item.name in seen or item.name not in record['files']:
                raise ValueError('REGULAR_PINNED_LEGACY_MEMBER_REQUIRED')
            content=archive.extractfile(item).read();sha=hashlib.sha256(content).hexdigest()
            if sha!=record['files'][item.name]:raise ValueError('PINNED_LEGACY_MEMBER_CHANGED')
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content);seen[item.name]=sha
    if seen!=record['files']:raise ValueError('COMPLETE_PINNED_LEGACY_CLOSURE_REQUIRED')
    return record
