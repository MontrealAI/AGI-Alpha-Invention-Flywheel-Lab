"""Reassemble byte-bound public audit records; no private keys or accounts."""
import argparse,hashlib,json,pathlib

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
 root=pathlib.Path(__file__).resolve().parents[1];index=json.loads((root/'RAW_OPERATING_INDEX.json').read_text())
 destination=pathlib.Path(args.output).expanduser().resolve()
 with destination.open('xb') as out:
  digest=hashlib.sha256();size=0
  for part in index['transport_parts']:
   raw=(root/part['path']).read_bytes()
   assert len(raw)==part['bytes'] and hashlib.sha256(raw).hexdigest()==part['sha256']
   out.write(raw);digest.update(raw);size+=len(raw)
 assert size==index['archive_bytes'] and digest.hexdigest()==index['archive_sha256']
 print(json.dumps({'accepted':True,'bytes':size,'sha256':digest.hexdigest(),'output':str(destination)}))

if __name__=='__main__':main()
