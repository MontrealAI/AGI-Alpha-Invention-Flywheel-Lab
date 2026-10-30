"""Reassemble byte-exact enterprise011 or adaptive012 ZIPs from bounded parts.

Both namespaces retain the same size, ordering, path, hash and CRC checks.
Adaptive012 transport additionally refuses its private simulation-key files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile


def reassemble(manifest, output):
    manifest, output = Path(manifest).absolute(), Path(output).absolute()
    if manifest.is_symlink() or any(p.is_symlink() for p in manifest.parents):
        raise ValueError('REGULAR_PART_MANIFEST_REQUIRED')
    data = json.loads(manifest.read_text())
    if set(data) != {'schema','archive_filename','archive_bytes','archive_sha256','parts'} or type(data['schema']) is not str or data['schema'] not in {'agi-alpha/enterprise011-package-parts/v1','agi-alpha/adaptive012-package-parts/v1'}:
        raise ValueError('EXACT_PART_MANIFEST_SCHEMA_REQUIRED')
    if type(data['archive_bytes']) is not int or not 1 <= data['archive_bytes'] <= 256_000_000 or not isinstance(data['parts'],list) or not 1 <= len(data['parts']) <= 256:
        raise ValueError('BOUNDED_PACKAGE_REQUIRED')
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError('NEW_UNSYMLINKED_ARCHIVE_OUTPUT_REQUIRED')
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        h, total = hashlib.sha256(), 0
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='enterprise011-pending-', delete=False) as stream:
            pending = Path(stream.name)
            for i, part in enumerate(data['parts']):
                if not isinstance(part,dict) or set(part) != {'path','offset','bytes','sha256'} or part['path'] != f'part-{i:03d}.bin' or type(part['offset']) is not int or part['offset'] != total or type(part['bytes']) is not int or not 1 <= part['bytes'] <= 4_000_000:
                    raise ValueError('ORDERED_UNIQUE_CONTIGUOUS_PARTS_REQUIRED')
                path = manifest.parent/part['path']
                if path.is_symlink() or not path.is_file() or path.stat().st_size != part['bytes']:
                    raise ValueError('REGULAR_COMPLETE_PART_REQUIRED')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != part['sha256']:
                    raise ValueError('PART_HASH_MISMATCH')
                stream.write(raw); h.update(raw); total += len(raw)
            stream.flush(); os.fsync(stream.fileno())
        if total != data['archive_bytes'] or h.hexdigest() != data['archive_sha256']:
            raise ValueError('COMPLETE_ARCHIVE_HASH_MISMATCH')
        with zipfile.ZipFile(pending) as z:
            if data['schema']=='agi-alpha/adaptive012-package-parts/v1' and any(name.endswith('.adaptive-simulation-key') for name in z.namelist()):
                raise ValueError('PRIVATE_SIMULATION_KEY_PUBLICATION_REFUSED')
            if z.testzip() is not None:
                raise ValueError('ARCHIVE_CRC_FAILURE')
        os.link(pending, output)
        return {'path': str(output), 'bytes': total, 'sha256': h.hexdigest(), 'parts_verified': len(data['parts'])}
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); print(json.dumps(reassemble(args.manifest,args.output)))


if __name__ == '__main__':
    main()
