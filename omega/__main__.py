"""Local intake → construct/import → independent check → portable report."""
from __future__ import annotations
import argparse
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from .runner import buyer, experiment

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>FLYWHEEL Ω | Water resilience probe</title>
<style>body{font:17px system-ui;max-width:960px;margin:45px auto;padding:20px;color:#17252b;background:#f5f7f6}h1{font-size:42px}textarea{width:100%;height:330px;font:14px monospace;padding:12px;box-sizing:border-box}button{padding:12px 24px;background:#154f49;color:white;border:0;border-radius:6px;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border-radius:8px}.tag{color:#ad591c}label{display:block;margin-top:16px}</style>
<h1>FLYWHEEL Ω</h1><p class="tag">Local research edition · no cloud calls · synthetic non-potable water</p>
<p>Construct a water-sharing blueprint, then check quality, capacity and voluntary participation. This does not certify physical safety or prove a new productive possibility.</p>
<label>Request JSON<textarea id="request">REQUEST</textarea></label>
<label>Optional proposal JSON from your own model account<textarea id="proposal" style="height:80px" placeholder="For external route only. We never call your provider or request keys."></textarea></label>
<p><button id="run">Construct and verify</button> <button id="save" disabled>Download certificate</button></p>
<p>Free/core release rights are unresolved. Proposed optional offers, in modeled USD: $299 self-hosted; $99 group session, at most 500/session; $20,000 founder 30-minute session. No checkout or booked service.</p>
<pre id="result">Edit the request and run locally.</pre>
<script>let receipt=null;document.getElementById('run').onclick=async()=>{let out=document.getElementById('result');try{let q=JSON.parse(document.getElementById('request').value),p=document.getElementById('proposal').value;let r=await fetch('/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:q,proposal:p?JSON.parse(p):null})});receipt=await r.json();out.textContent=JSON.stringify(receipt,null,2);document.getElementById('save').disabled=!r.ok||!receipt.certificate}catch(e){receipt=null;out.textContent=String(e);document.getElementById('save').disabled=true}};document.getElementById('save').onclick=()=>{let a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}));a.href=u;a.download='omega-certificate.json';a.click();URL.revokeObjectURL(u)};</script></html>'''


def serve(root, port):
    page = PAGE.replace('REQUEST', html.escape((root/'omega/request.json').read_text())).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page)
        def do_POST(self):
            # Loopback only; reject cross-site writes and large requests.
            if self.path != '/solve':
                self.send_error(404); return
            origin = self.headers.get('Origin')
            if origin is not None and origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
                self.send_error(403); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 100000:
                    raise ValueError('REQUEST_TOO_LARGE_OR_EMPTY')
                body = json.loads(self.rfile.read(length))
                value = buyer(body['request'], body.get('proposal'))
                status = 200
            except (ValueError, KeyError, TypeError, RuntimeError) as error:
                value, status = {'error': str(error)}, 400
            encoded = json.dumps(value).encode()
            self.send_response(status); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(encoded)
    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'Local only: http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    solve=commands.add_parser('solve'); solve.add_argument('--request',required=True); solve.add_argument('--proposal'); solve.add_argument('--output',required=True)
    compare=commands.add_parser('experiment'); compare.add_argument('--output',required=True)
    web=commands.add_parser('serve'); web.add_argument('--port',type=int,default=8879)
    args=parser.parse_args(); root=Path(__file__).resolve().parents[1]
    if args.command=='serve':
        serve(root,args.port); return
    if args.command=='solve':
        value=buyer(json.loads(Path(args.request).read_text()),json.loads(Path(args.proposal).read_text()) if args.proposal else None)
    else:
        value=experiment(root)
    destination=Path(args.output)
    with destination.open('x') as handle:
        json.dump(value,handle,indent=2,sort_keys=True); handle.write('\n')
    print(destination)


if __name__=='__main__': main()
