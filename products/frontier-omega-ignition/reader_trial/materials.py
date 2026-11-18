"""Receive the two registered public papers and build only the assigned local workflow."""
from hashlib import file_digest
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
RESEARCH = PRODUCT.parents[1] / "docs" / "research"
REG = json.loads((HERE / "REGISTERED.json").read_text())
ARMS = ("A", "B", "C", "D")
STYLE = """body{margin:2rem auto;max-width:68rem;padding:0 1rem;font:1.1rem/1.6 system-ui;color:#181322;background:#fcfaf7}h1,h2{line-height:1.15}a{color:#45276d}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #8c561c}label{display:block;margin:.8rem 0}.field{display:block;width:min(100%,42rem);box-sizing:border-box;font:inherit}input,button,select,textarea{font:inherit}button{padding:.35rem .7rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #bbb;margin-top:1.4rem;padding:.5rem}li{margin:.5rem 0}"""
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'"


def sha(path):
    with path.open("rb") as fh:
        return file_digest(fh, "sha256").hexdigest()


def shell(lang, title, body):
    return f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{CSP}"><title>{escape(title)}</title><style>{STYLE}</style><main><h1>{escape(title)}</h1>{body}</main></html>'


def script_data(obj):
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def sources(lang):
    spec = REG["languages"][lang]
    files = {fmt: RESEARCH / f"{spec['paper']}.{fmt}" for fmt in ("html", "pdf")}
    if any(sha(p) != spec[fmt + "_sha256"] for fmt, p in files.items()):
        raise ValueError("Public source identity differs from registration.")
    return files


def pages(pdf):
    data = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
                          capture_output=True, check=True).stdout.decode().split("\f")
    return data[:-1] if data and not data[-1] else data


def build(lang, arm, destination):
    files = sources(lang)
    destination.mkdir()
    for f in files.values():
        shutil.copyfile(f, destination / f.name)
    en = lang == "en"
    label = "Open physical PDF page" if en else "Ouvrir la page physique du PDF"
    links = [(files["html"].name, "Author's original reading guide" if en else "Guide original de l’auteur"),
             (files["pdf"].name, "Original PDF" if en else "PDF original")]
    if arm == "C":
        subprocess.run([sys.executable, "-B", str(PRODUCT / "reading_room/edition.py"),
                        "--source", str(files["html"]), "--pdf", str(files["pdf"]),
                        "--output", str(destination / "edition")], check=True, capture_output=True)
        links.append(("edition/index.html", "Passage edition" if en else "Édition par passage"))
    if arm in ("B", "D"):
        texts = pages(files["pdf"])
        if len(texts) != REG["languages"][lang]["pdf_pages"]:
            raise ValueError("Physical page count differs from registration.")
        if arm == "B":
            sections = [f'<article><h2><a href="{files["pdf"].name}#page={n}">{label} {n}</a></h2><pre>{escape(t)}</pre></article>' for n,t in enumerate(texts, 1)]
            title = "Full paper with page index" if en else "Texte intégral avec index des pages"
            body = ('<p>Use your browser’s Find command to locate a word or phrase.</p>' if en else
                    '<p>Utilisez la recherche du navigateur pour repérer un mot ou une expression.</p>') + "".join(sections)
        else:
            title = "Search passages by physical page" if en else "Rechercher les passages par page physique"
            instructions = ("Enter terms to find pages containing all of them. Use double quotation marks to match consecutive terms in order. Check the original page for layout, units and meaning."
                            if en else "Saisissez des termes pour trouver les pages qui les contiennent tous. Utilisez les guillemets pour rechercher des termes consécutifs dans le même ordre. Vérifiez la disposition, les unités et le sens sur la page originale.")
            body = f'<label>{instructions}<input class="field" id="query" type="search"></label><p id="summary" role="status"></p><div id="hits"></div>'
            body += '<script type="application/json" id="pages">' + script_data(texts) + '</script><script>'
            body += 'const pdf=' + json.dumps(files["pdf"].name) + ';const label=' + json.dumps(label) + ';'
            body += (HERE / "concordance.js").read_text() + '</script>'
        (destination / "index-pages.html").write_text(shell(lang,title,body),encoding="utf-8")
        links.append(("index-pages.html", title))
    title = "Publication workspace" if en else "Espace de lecture"
    (destination / "index.html").write_text(shell(lang,title,"<ul>"+"".join(
        f'<li><a href="{link}">{escape(text)}</a></li>' for link,text in links)+"</ul>"),encoding="utf-8")
