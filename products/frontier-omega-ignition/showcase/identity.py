"""Draw a publication plate from the registered audit. SVG needs only the standard library."""
import argparse
import html
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT / "flagship"))
from pairing_lab import PUBLIC_HASH, analyze, digest  # noqa: E402

INK = "#f6f0e6"
MUTED = "#c6bfd0"
GOLD = "#ecd6a6"
LILAC = "#c7b3e3"
LINE = "#61576d"
SERIF = "Georgia,'Liberation Serif',serif"
SANS = "'Helvetica Neue',Arial,'Liberation Sans',sans-serif"
MONO = "'Liberation Mono',monospace"


def num(v):
    return f"{v:.2f}"


def plate():
    raw = (PRODUCT / "flagship" / "runs.csv").read_bytes()
    if digest(raw) != PUBLIC_HASH:
        raise ValueError("registered public input changed")
    one = analyze(raw, width=1, witnesses=True)
    pair = analyze(raw, width=2, witnesses=True)
    receipt = json.loads((PRODUCT / "flagship" / "receipt.json").read_bytes())
    for result in (one, pair):
        frozen = receipt["arms"][f'2000000/{result["parameters"]["width"]}']
        if (result["selected"] != frozen["selected"] or
                {k: v for k,v in result["audit"].items() if k != "witnesses"} != frozen["audit"]):
            raise ValueError("reproduced scores differ from recorded results")
    base, = one["selected"]
    extra, = set(pair["selected"]) - {base}
    labels = {"qwen/agentless": "Qwen3-Coder-Next / Agentless",
              "glm/acr": "GLM-4.7-Flash / AutoCodeRover"}
    cases = []
    for witness in pair["audit"]["witnesses"]:
        measured = {p["stack"]: p["solved"] for p in witness["attempts"]}
        cases.append((witness["task"], measured[base], measured[extra]))
    if len(cases) != 40:
        raise ValueError("this figure is registered for the 40-issue audit")
    added = [(i, task) for i,(task,a,b) in enumerate(cases,1) if b and not a]
    saved = pair["audit"]["solved"] - one["audit"]["solved"]
    delta = pair["audit"]["tokens"] - one["audit"]["tokens"]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="3200" height="2000" viewBox="0 0 1600 1000" role="img" aria-labelledby="title desc">',
             '<title id="title">Pairing Lab. Forty held-out software issues.</title>',
             '<desc id="desc">Each angular position is one observed issue. Inner marks show the primary stack, '
             'outer marks the added stack. Filled marks indicate a passing patch. Gold diamonds identify the '
             'two additional issues resolved by the added stack. The data are historical independent grades.</desc>',
             '<defs><radialGradient id="field" cx=".55" cy=".44" r=".78"><stop stop-color="#30263c"/>'
             '<stop offset="1" stop-color="#181624"/></radialGradient></defs>',
             '<rect width="1600" height="1000" fill="#181624"/>',
             '<rect x="825" y="146" width="707" height="587" rx="1" fill="url(#field)" stroke="#53495e"/>']
    def txt(x,y,s,size,color=INK,family=SANS,weight=400,spacing=0,anchor="start",italic=False):
        parts.append(f'<text x="{num(x)}" y="{num(y)}" font-size="{size}" fill="{color}" '
                     f'font-family="{family}" font-weight="{weight}" letter-spacing="{spacing}" '
                     f'text-anchor="{anchor}" font-style="{"italic" if italic else "normal"}">{html.escape(str(s))}</text>')
    def line(x1,y1,x2,y2,c=LINE,w=1):
        parts.append(f'<path d="M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}" stroke="{c}" stroke-width="{w}" fill="none"/>')
    def circle(x,y,r,stroke,fill="none",sw=1):
        parts.append(f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(r)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    def diamond(x,y,r,fill):
        parts.append(f'<path d="M{num(x)} {num(y-r)} l{num(r)} {num(r)} -{num(r)} {num(r)} -{num(r)} -{num(r)} Z" fill="{fill}"/>')
    def micro(x,y,s,c=MUTED,anchor="start"):
        txt(x,y,s,14,c,MONO,400,1.7,anchor)

    circle(91,73,24,"#ad956c")
    txt(91,82,"Ω",30,GOLD,SERIF,400,0,"middle")
    txt(132,70,"FRONTIER Ω",23,INK,SANS,600,2)
    txt(133,92,"IGNITION",13,MUTED,MONO,400,2.4)
    txt(1532,78,"MONTREAL.AI  ×  QUEBEC.AI",17,INK,SANS,600,1.7,"end")
    line(68,118,1532,118)
    micro(69,189,"THE INSTRUMENT",GOLD)
    txt(66,296,"Pairing Lab",112,INK,SERIF,400,-5)
    txt(69,357,"Which self-hosted coding stacks",37,INK,SERIF)
    txt(69,406,"merit a private pilot?",37,INK,SERIF)
    txt(69,467,"We selected on 60 issues, then tested on 40 held out.",23,MUTED)
    txt(69,505,"A second stack raised coverage from 16 issues to 18.",23,MUTED)
    audit_cap_millions = pair["parameters"]["budget"] * len(cases) / 1e6
    txt(69,543,f"Each route could use {audit_cap_millions:g}M tokens across all {len(cases)} issues.",23,MUTED)
    line(69,587,750,587)
    txt(70,652,f'+{saved}',61,GOLD,SERIF)
    txt(327,652,f'+{delta / 1e6:.2f}M',61,GOLD,SERIF)
    micro(70,691,"RESOLVED ISSUES")
    micro(330,691,"CHARGED TOKENS")
    micro(853,184,"HELD-OUT ISSUE AUDIT",GOLD)
    micro(1504,184,"40 ISSUES",MUTED,"end")
    cx,cy=1178,437
    def point(radius,deg):
        a=math.radians(deg)
        return cx+radius*math.cos(a),cy+radius*math.sin(a)
    for r in (135,165,194):
        circle(cx,cy,r,"#564b63" if r != 194 else "#443c4e")
    for index,(task,a,b) in enumerate(cases,1):
        deg=-90 + 360*(index-1)/len(cases)
        inner=point(135,deg)
        outer=point(165,deg)
        outermost=point(194,deg)
        parts.append(f'<g><title>{index:02} · {html.escape(task)} · primary {a} · added {b}</title>')
        line(*point(125,deg),*point(174,deg),"#675b74" if a or b else "#4c4257")
        circle(*inner,6, LILAC if a else "#80768b", LILAC if a else "#282333",1.3)
        if b and not a:
            diamond(*outer,8,GOLD)
        else:
            circle(*outer,6,LILAC if b else "#80768b",LILAC if b else "#282333",1.3)
        if index in (1,10,20,30) or (b and not a):
            t=point(213,deg)
            line(*point(184,deg),*outermost,GOLD if b and not a else "#83778f")
            txt(t[0],t[1]+5,f'{index:02}',15,GOLD if b and not a else MUTED,MONO,400,0,"middle")
        parts.append('</g>')
    txt(cx,cy+1,f'{pair["audit"]["solved"]} / {len(cases)}',58,INK,SERIF,400,-2,"middle")
    txt(cx,cy+31,"ISSUES RESOLVED",12,MUTED,MONO,400,1.3,"middle")
    line(853,675,1504,675)
    circle(861,705,5,LILAC,LILAC)
    txt(875,711,"Passing patch",17,MUTED)
    circle(1034,705,5,"#a99ab7","none",1.3)
    txt(1048,711,"Did not pass",17,MUTED)
    diamond(1215,705,6,GOLD)
    txt(1230,711,"Added resolution",17,GOLD)
    line(68,764,1532,764)
    micro(69,802,"ADDITIONAL RESOLUTIONS",GOLD)
    for y, (idx, task) in zip((847,884), added):
        txt(69,y,f'{idx:02}',17,GOLD,MONO)
        txt(116,y,task,22,INK,MONO)
    micro(715,802,"HOW TO READ THE PLATE",GOLD)
    txt(716,842,"Inner ring",19,MUTED)
    txt(843,842,labels[base],21,INK)
    txt(716,881,"Outer ring",19,MUTED)
    txt(843,881,labels[extra],21,INK)
    line(68,913,1532,913)
    txt(69,949,"Data: Zhao, Poskitt & Lo · Pairing Matters · Figshare v1 · CC BY 4.0",17,MUTED)
    txt(69,977,"October 2026 archive · Retrospective union of independently graded patches. Both attempts contribute their reported token volume.",16,MUTED)
    txt(1532,949,"17 NOV 2026",15,GOLD,MONO,400,1,"end")
    parts.append('</svg>')
    return "\n".join(parts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path,help="destination .svg or .png; PNG is 3200 by 2000 pixels")
    target=p.parse_args().output
    doc=plate()
    if target.suffix == ".svg":
        target.write_text(doc,encoding="utf-8")
    elif target.suffix == ".png":
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"identity.svg"
            src.write_text(doc,encoding="utf-8")
            if shutil.which("inkscape"):
                subprocess.run(["inkscape",str(src),"--export-type=png",f"--export-filename={target.resolve()}"],check=True)
            elif shutil.which("rsvg-convert"):
                subprocess.run(["rsvg-convert",str(src),"-o",str(target)],check=True)
            else:
                p.error("PNG requires Inkscape or rsvg-convert. SVG generation uses only Python.")
    else:
        p.error("choose a .png or .svg destination")


if __name__=="__main__":
    main()
