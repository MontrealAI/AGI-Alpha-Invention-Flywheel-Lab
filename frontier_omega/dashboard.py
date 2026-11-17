"""Private, accessible static browser dossier for the FRONTIER Ω reservoir."""
from __future__ import annotations

from html import escape as html
import json
import os
from pathlib import Path
import uuid


def esc(x):
    return html(str(x), quote=True)


def dashboard(report):
    """No external assets, network calls or executable customer code."""
    stats = report["counts"]
    by_id = {}
    for event in report["retest_signals"]:
        by_id.setdefault(event["problem_id"], []).append(event["frontier_id"])
    cards = []
    for p in report["inventory"]:
        links = "".join('<a target="_blank" rel="noopener noreferrer" href="' + esc(url) +
                        '">Primary evidence ↗</a>' for url in p["source_urls"])
        chips = "".join("<span class='chip'>" + esc(tag.replace("-", " ")) + "</span>"
                        for tag in p["tags"])
        matches = by_id.get(p["id"], [])
        alternatives = "".join("<li><b>" + esc(a["name"]) + "</b> — " +
                               esc(a["route"]) + "</li>" for a in p["alternatives"])
        cards.append('<article class="dossier" data-search="' +
                     esc((p["title"] + " " + p["beneficiary"] + " " + " ".join(p["tags"])).lower()) +
                     '"><div class="status">PUBLIC SIGNAL · DEMAND UNVERIFIED</div><h2>' +
                     esc(p["title"]) + '</h2><p class="beneficiary">' + esc(p["beneficiary"]) +
                     '</p><div class="chips">' + chips +
                     '</div><div class="section-label">TARGET OUTCOME</div><p>' +
                     esc(p["outcome"]) + '</p><div class="section-label">CURRENT BLOCKER</div><p>' +
                     esc(p["blocker"]) + '</p><div class="section-label">DECISIVE TEST</div><p>' +
                     esc(p["next_test"]) + '</p><details><summary>Acceptance & strongest alternatives</summary><p>' +
                     esc(p["acceptance"]) + '</p><ul>' + alternatives +
                     '</ul></details><footer><span>' + str(len(matches)) +
                     ' capability matches · retest suggested only</span><div class="refs">' + links +
                     '</div></footer></article>')
    css = r"""
:root{color-scheme:dark;--bg:#090d19;--pane:#151b2c;--hair:#303a50;--text:#f0eef6;--muted:#b9c0d1;--gold:#e7cd94;--purple:#b9a3ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 70% -10%,#342b5b 0%,transparent 44%),radial-gradient(ellipse at 0% 35%,#112e39 0%,transparent 42%),var(--bg);color:var(--text);font:16px/1.62 system-ui,-apple-system,sans-serif}
main{max-width:1260px;margin:auto;padding:clamp(22px,5vw,72px)}
header{border-bottom:1px solid var(--hair);padding-bottom:34px} .eyebrow{color:var(--gold);font-size:12px;letter-spacing:.2em;font-weight:800}
h1{font-size:clamp(38px,6vw,82px);line-height:1.06;letter-spacing:-.055em;margin:15px 0 9px}h1 span{color:var(--gold)}
.subtitle{max-width:750px;color:var(--muted);font-size:18px;margin:0}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:30px 0}
.metric{border:1px solid var(--hair);background:#141b2cbc;padding:19px;border-radius:14px;min-width:0}
.metric strong{display:block;font-size:clamp(24px,4vw,41px);font-weight:720;line-height:1.1;color:var(--gold)}
.metric span{font-size:12px;color:var(--muted)}
.toolrow{display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:33px 0 18px}
.toolrow h2{font-size:24px;letter-spacing:-.035em;margin:0}
input{border:1px solid #65708a;border-radius:12px;background:#182032;color:white;padding:13px 18px;min-width:min(320px,100%);font:inherit}
input:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.dossier{border:1px solid var(--hair);background:linear-gradient(150deg,#1d2336,#121929);border-radius:19px;padding:clamp(19px,3vw,30px);min-width:0;box-shadow:0 13px 35px #0002}
.dossier h2{font-size:23px;letter-spacing:-.03em;line-height:1.2;margin:12px 0}.status,.section-label{font-size:10px;letter-spacing:.17em;font-weight:850}
.status{color:#c0aaff}.beneficiary{font-size:13px;color:var(--muted);margin:4px 0 16px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0}.chip{border-radius:999px;border:1px solid #535a72;color:#c7d4ea;font-size:11px;padding:3px 9px;text-transform:capitalize}
.section-label{color:var(--gold);margin:20px 0 6px}.dossier p{margin:0}details{margin:20px 0 0;border-top:1px solid var(--hair);padding-top:11px}
summary{cursor:pointer;color:#d1c4fd;font-weight:650}details p{margin:13px 0!important}li{margin:7px 0}
footer{border-top:1px solid var(--hair);margin-top:22px;padding-top:17px;font-size:12px;color:var(--muted)}
.refs{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}
a{color:#dcc6ff;text-decoration:none;border-bottom:1px dotted #dcc6ff}a:hover{text-decoration:underline}
.qualification{padding:23px;border-left:3px solid var(--gold);color:var(--muted);background:#191f30;border-radius:5px;margin:36px 0}
.qualification strong{color:var(--text)}
#none{display:none;color:var(--muted);padding:35px}
@media(max-width:800px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:450px){main{padding:20px}.metrics{gap:9px}.metric{padding:14px}input{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""
    js = r"""
(function(){
 const q=document.getElementById('filter'),cards=[...document.querySelectorAll('.dossier')],none=document.getElementById('none');
 q.addEventListener('input',function(){
   const term=this.value.trim().toLowerCase();let visible=0;
   for(const card of cards){const show=card.dataset.search.includes(term);card.hidden=!show;visible+=show?1:0;}
   none.style.display=visible?'none':'block';
 });
})();
"""
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>FRONTIER Ω — Opportunity Reservoir</title><style>' + css + '</style>'
            '<main><header><div class="eyebrow">MONTREAL.AI · ALPHA ECONOMIC ENGINE</div>'
            '<h1>FRONTIER <span>Ω</span></h1><p class="subtitle">'
            'An accumulating reservoir of valuable blocked outcomes. '
            'When AI capabilities advance, retest what may have become possible.</p></header>'
            '<div class="metrics"><div class="metric"><strong>' + str(stats["problems"]) +
            '</strong><span>Problem dossiers</span></div><div class="metric"><strong>' +
            str(stats["capability_observations"]) +
            '</strong><span>Frontier observations</span></div><div class="metric"><strong>' +
            str(stats["retest_signals"]) + '</strong><span>Retest signals</span></div>'
            '<div class="metric"><strong>0</strong><span>Verified paid outcomes in this reservoir</span></div></div>'
            '<div class="qualification"><strong>Investigation system—not a revenue ledger.</strong> '
            'Public technical sources do not establish buyer authorization, independent frontier crossings, '
            'production success or collectible earnings. Every recommended retest requires real evidence.</div>'
            '<div class="toolrow"><h2>Opportunity inventory</h2>'
            '<label for="filter">Search dossiers <input id="filter" type="search" autocomplete="off" '
            'placeholder="Search outcomes, sectors, capabilities"></label></div>'
            '<div class="grid">' + "".join(cards) + '</div>'
            '<p id="none" role="status">No dossiers match your search.</p>'
            '<p class="qualification">The watch process can add private records without manual database edits. '
            'Signals are advisory only; no real customers, payments, deployment or spending authority are inferred.</p>'
            '</main><script>' + js + '</script></html>')


def write_dashboard(reservoir, filename="FRONTIER-OMEGA.html"):
    path = reservoir.root / filename
    if "/" in filename or filename.startswith(".") or not filename.endswith(".html"):
        raise ValueError("PRIVATE_OUTPUT_FILENAME_REQUIRED")
    if path.is_symlink() or (path.exists() and path.stat().st_nlink != 1):
        raise ValueError("UNSAFE_DASHBOARD_OUTPUT")
    payload = dashboard(reservoir.report()).encode("utf-8")
    temporary = reservoir.root / ("." + uuid.uuid4().hex + ".tmp")
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"private_dashboard": str(path), "bytes": len(payload),
            "external_assets": 0, "commercial_qualification": "NOT_ESTABLISHED"}
