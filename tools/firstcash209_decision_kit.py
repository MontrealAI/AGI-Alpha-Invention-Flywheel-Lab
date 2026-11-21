#!/usr/bin/env python3
"""FIRSTCASH209: offline, evidence-bound bilingual decision-kit assembler.

This is an engineering delivery instrument, not autonomous discovery, buyer
acceptance, a financial account, or proof of commercial revenue.
"""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "firstcash209/public-decision-case/v1"
COST_KEYS = (
    "research", "acquisition", "production", "verification", "correction",
    "support", "maintenance", "taxes", "refunds", "infrastructure",
    "failure", "capital", "financing",
)
TEXT_KEYS = ("en", "fr")
OPTION_KEYS = {
    "id", "title", "productive_mean", "accepted_outcome", "strongest_alternative",
    "falsification", "sources", "complete_costs_cad", "verdict",
}
FILE_NAMES = ("CASE.json", "DECISION.json", "DECISION.html")
MAX_BYTES = 256_000


class Refusal(ValueError):
    """An input or proof does not meet this bounded contract."""


def refuse(code):
    raise Refusal(code)


def no_duplicate_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            refuse("DUPLICATE_JSON_KEY:" + k)
        out[k] = v
    return out


def json_load_bytes(raw):
    if len(raw) > MAX_BYTES:
        refuse("INPUT_SIZE_BOUND")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_pairs,
                          parse_constant=lambda _: refuse("NONFINITE_NUMBER"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Refusal("INVALID_UTF8_JSON") from e


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_text(value, field):
    if not isinstance(value, str) or not 3 <= len(value.strip()) <= 240:
        refuse("TEXT_REQUIRED_OR_TOO_LONG:" + field)
    if any(ord(c) < 32 for c in value):
        refuse("TEXT_CONTROL_CHARACTER:" + field)
    return value.strip()


def bilingual(obj, field):
    if not isinstance(obj, dict) or set(obj) != set(TEXT_KEYS):
        refuse("BILINGUAL_REQUIRED:" + field)
    for lang in TEXT_KEYS:
        validate_text(obj[lang], field + "." + lang)
    return obj


def validate(case):
    if not isinstance(case, dict) or set(case) != {
        "schema", "case_id", "kind", "as_of", "beneficiary", "desired_outcome", "options"
    }:
        refuse("CASE_FIELDS")
    if case["schema"] != SCHEMA:
        refuse("SCHEMA_MISMATCH")
    if case["kind"] not in ("public_self_case", "synthetic_fixture"):
        refuse("NOT_AUTHORIZED_PUBLIC_CASE_KIND")
    if not isinstance(case["case_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,48}", case["case_id"]):
        refuse("INVALID_CASE_ID")
    if not isinstance(case["as_of"], str) or not re.fullmatch(r"20\d\d-\d\d-\d\d", case["as_of"]):
        refuse("INVALID_CASE_DATE")
    import datetime
    try:
        datetime.date.fromisoformat(case["as_of"])
    except ValueError as e:
        raise Refusal("INVALID_CASE_DATE") from e
    bilingual(case["beneficiary"], "beneficiary")
    bilingual(case["desired_outcome"], "desired_outcome")
    options = case["options"]
    if not isinstance(options, list) or len(options) != 3:
        refuse("THREE_MATERIAL_OPTIONS_REQUIRED")
    seen = set()
    no_deploy_count = 0
    for index, option in enumerate(options):
        if not isinstance(option, dict) or set(option) != OPTION_KEYS:
            refuse("OPTION_FIELDS")
        oid = option["id"]
        if not isinstance(oid, str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,32}", oid) or oid in seen:
            refuse("INVALID_OR_DUPLICATE_OPTION")
        seen.add(oid)
        for field in ("title", "productive_mean", "accepted_outcome",
                      "strongest_alternative", "falsification"):
            bilingual(option[field], f"options[{index}].{field}")
        verdict = option["verdict"]
        if verdict not in ("HOLD", "NO_DEPLOY"):
            refuse("UNVERIFIED_DEPLOY_OR_FINANCIAL_CLAIM")
        no_deploy_count += verdict == "NO_DEPLOY"
        costs = option["complete_costs_cad"]
        if not isinstance(costs, dict) or set(costs) != set(COST_KEYS):
            refuse("INCOMPLETE_COST_DISCLOSURE")
        for key, value in costs.items():
            if value is not None and (type(value) not in (int, float) or not 0 <= value <= 1e9):
                refuse("INVALID_COMPLETE_COST:" + key)
        sources = option["sources"]
        if not isinstance(sources, list) or not 1 <= len(sources) <= 5:
            refuse("EACH_OPTION_REQUIRES_SOURCE")
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"url", "sha256", "scope"}:
                refuse("SOURCE_FIELDS")
            url = source["url"]
            if not isinstance(url, str) or len(url) > 420:
                refuse("SOURCE_URL")
            try:
                parts = urlsplit(url)
                valid = (parts.scheme == "https" and bool(parts.hostname)
                         and parts.username is None and parts.password is None
                         and parts.port in (None, 443) and not any(c.isspace() for c in url)
                         and not parts.hostname.endswith(".local"))
            except ValueError:
                valid = False
            if not valid:
                refuse("SOURCE_MUST_BE_PUBLIC_HTTPS")
            if source["scope"] not in ("primary_public_record", "provider_claim", "internal_public_research", "synthetic_control"):
                refuse("SOURCE_SCOPE")
            sha = source["sha256"]
            if sha is not None and (not isinstance(sha, str) or not re.fullmatch("[0-9a-f]{64}", sha)):
                refuse("SOURCE_HASH_INVALID")
    if no_deploy_count != 1:
        refuse("EXACTLY_ONE_NO_DEPLOY_OPTION_REQUIRED")
    return case


def esc(s):
    return html.escape(str(s), quote=True)


def options_table(options, lang, prop):
    rows = "".join(
        f"<tr><th>{esc(o['title'][lang])}</th><td>{esc(o[prop][lang])}</td><td>{o['verdict']}</td></tr>"
        for o in options
    )
    return "<table><thead><tr><th>Option</th><th>Evidence-bound description</th><th>Gate</th></tr></thead><tbody>" + rows + "</tbody></table>"


def pair(en, fr):
    return f'<div class="pair"><section lang="en"><h3>English</h3>{en}</section><section lang="fr"><h3>Français</h3>{fr}</section></div>'


def para(s):
    return f"<p>{esc(s)}</p>"


def page(number, title_en, title_fr, body, note):
    return (f'<article class="sheet" data-page="{number}">'
            f'<header><span>FRONTIER Ω · MONTREAL.AI</span><span>{number:02} / 10</span></header>'
            f'<h2>{esc(title_en)} <small>{esc(title_fr)}</small></h2>'
            f'{body}<footer>{esc(note)} · FIRSTCASH209 · NO CLIENT OR PAYMENT CLAIM</footer></article>')


def make_html(case, source_sha):
    o = case["options"]
    cites = []
    for item in o:
        for s in item["sources"]:
            cites.append(f"<li><b>{esc(item['id'])} · {esc(s['scope'])}</b> — "
                         f'<a href="{esc(s["url"])}">{esc(s["url"])}</a>'
                         f'<br>Source-byte digest: {esc(s["sha256"] or "NOT INDEPENDENTLY VERIFIED")}</li>')
    option_cards = "".join(f'<div class="card"><h3>{esc(x["title"]["en"])} / {esc(x["title"]["fr"])}</h3>'
                          f'<p>{esc(x["accepted_outcome"]["en"])}</p><p>{esc(x["accepted_outcome"]["fr"])}</p>'
                          f'<b>{x["verdict"]}</b></div>' for x in o)
    cost_rows = "".join(f"<tr><td>{esc(k)}</td>" +
                        "".join(f"<td>{esc(x['complete_costs_cad'][k]) if x['complete_costs_cad'][k] is not None else 'UNKNOWN'}</td>" for x in o)
                        + "</tr>" for k in COST_KEYS)
    pages = []
    pages.append(page(1, "The decision", "La décision",
                      f'<p class="hero">{esc(case["beneficiary"]["en"])} · {esc(case["beneficiary"]["fr"])}</p>' +
                      pair(para(case["desired_outcome"]["en"]), para(case["desired_outcome"]["fr"])) +
                      '<div class="warning">PUBLIC SELF-CASE / SYNTHETIC CASE. Not a purchased dossier, accepted outcome, actual client or cash receipt.</div>',
                      "Scope bounded"))
    pages.append(page(2, "Outcome before technology", "Résultat avant la technologie",
                      pair(para(case["desired_outcome"]["en"]) + "<p>Assess the complete accepted outcome, not a model demonstration.</p>",
                           para(case["desired_outcome"]["fr"]) + "<p>Évaluer le résultat complet accepté, et non une démonstration de modèle.</p>") +
                      "<h3>Candidate arrangements</h3>" + option_cards, "Three complete alternatives"))
    pages.append(page(3, "Productive means", "Moyens productifs",
                      pair(options_table(o, "en", "productive_mean"),
                           options_table(o, "fr", "productive_mean")), "Mechanism hypotheses, not proven deployments"))
    pages.append(page(4, "The strongest alternative", "La meilleure solution existante",
                      pair(options_table(o, "en", "strongest_alternative"),
                           options_table(o, "fr", "strongest_alternative")), "No weakened or fictitious incumbent"))
    pages.append(page(5, "How to falsify it", "Comment le réfuter",
                      pair(options_table(o, "en", "falsification"),
                           options_table(o, "fr", "falsification")), "Predeclared tests, not acceptance certificates"))
    pages.append(page(6, "Sources and provenance", "Sources et provenance",
                      '<p>Source links are supplied by the case author. A URL alone is not independent byte verification. '
                      'Les liens sont fournis par l’auteur; une URL seule ne vérifie pas les octets.</p><ol class="sources">' +
                      "".join(cites) + "</ol>", "Source hashes may be unknown"))
    pages.append(page(7, "Complete costs", "Coûts complets",
                      "<p>Amounts are CAD input hypotheses only. UNKNOWN prevents any profit declaration. "
                      "Montants en CAD fournis, non vérifiés; une valeur inconnue interdit toute déclaration de bénéfice.</p>" +
                      '<table><thead><tr><th>Cost</th>' +
                      "".join(f"<th>{esc(x['id'])}</th>" for x in o) +
                      "</tr></thead><tbody>" + cost_rows + "</tbody></table>",
                      "No invented expenses or financing"))
    pages.append(page(8, "Buyer participation", "Participation volontaire",
                      pair("<p>Compare an independent capable human, AI provider, self-service and no purchase. "
                           "Buyer permission, settlement and delivery acceptance are not present in these source records.</p>",
                           "<p>Comparer une personne compétente, un fournisseur IA, le libre-service et aucun achat. "
                           "Consentement, règlement et acceptation de livraison ne sont pas attestés ici.</p>") +
                      "<h3>Disclosure</h3><p>Observed page availability, published prices and simulated demand are not collected revenue.</p>",
                      "Buyer choice remains unobserved"))
    pages.append(page(9, "The operating gate", "Le seuil opérationnel",
                      pair("<p>Actual outsider payment → authentic settlement → scoped custom delivery → independent acceptance "
                           "→ complete-cost reconciliation → repeatable second order. With no verified buyer, HOLD.</p>",
                           "<p>Paiement externe réel → règlement authentifié → livraison personnalisée → acceptation "
                           "indépendante → coûts complets → deuxième commande distincte. Sans acheteur vérifié, SUSPENDRE.</p>") +
                      "<p>Financial custody remains in the existing canonical account; this document cannot authorize new reservations.</p>",
                      "No transaction, no second account"))
    pages.append(page(10, "Keep the proof portable", "Conserver une preuve portable",
                      pair("<p>Re-run the offline verifier against frozen CASE.json, DECISION.json, HTML and SHA256 manifest. "
                           "Modification, missing sources or a changed program must fail.</p>",
                           "<p>Rejouer la vérification locale des fichiers figés, de leurs empreintes et du programme. "
                           "Toute modification doit être refusée.</p>") +
                      f'<p class="mono">Frozen case SHA256: {esc(source_sha)}</p>' +
                      "<p>Engineering artifact only; no verified independent buyer, frontier novelty, profit or recursive advantage.</p>",
                      "Source-bound and explicitly conditional"))
    style = """
    @page{size:A4;margin:0}
    *{box-sizing:border-box}body{margin:0;background:#efedf4;color:#21172f;font:13px/1.42 Georgia,serif}
    .sheet{background:#fff;width:210mm;min-height:297mm;margin:15px auto;padding:17mm 18mm;page-break-after:always;break-after:page;position:relative;box-shadow:0 4px 22px #24203920}
    .sheet:last-child{break-after:auto}.sheet header{border-top:5px solid #281146;display:flex;justify-content:space-between;padding:10px 0;color:#281146;font:700 10px system-ui;letter-spacing:.1em}
    h2{font-size:29px;line-height:1.08;color:#281146;margin:25px 0}h2 small{font-size:17px;color:#9b742a;display:block;margin-top:8px;font-weight:normal}
    h3{color:#43235e;font:700 13px system-ui;margin:17px 0 8px}.hero{font-size:21px;color:#7f5720}
    .pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pair section+section{border-left:1px solid #cbbddd;padding-left:17px}
    .card,.warning{background:#f5f1f9;padding:11px;margin:12px 0;border-left:3px solid #a67c29}
    p{margin:9px 0}table{width:100%;border-collapse:collapse;font:10px/1.35 system-ui;overflow-wrap:anywhere;table-layout:fixed}
    td,th{padding:7px 5px;border-bottom:1px solid #d4c9df;text-align:left;vertical-align:top}
    .sources{font:11px/1.3 system-ui;overflow-wrap:anywhere}.sources li{margin:8px 0}a{color:#4c3076}
    footer{position:absolute;bottom:10mm;left:18mm;right:18mm;border-top:1px solid #d4c9df;padding-top:8px;color:#615674;font:10px system-ui}
    .mono{font:10px monospace;overflow-wrap:anywhere}
    @media print{body{background:white}.sheet{height:297mm;min-height:0;margin:0;box-shadow:none;overflow:hidden;print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    @media(max-width:750px){.sheet{width:100%;min-height:0;padding:25px 20px 60px}.pair{display:block}.pair section+section{border-left:0;border-top:1px solid #cbbddd;padding-left:0;margin-top:15px}footer{left:20px;right:20px}h2{font-size:24px}}
    """
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>FRONTIER Ω · Source-bound bilingual decision kit</title>'
            '<style>' + style + '</style></head><body><main>'
            + "".join(pages) + "</main></body></html>\n").encode("utf-8")


def checked_path(root, name):
    path = root / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        refuse("UNSAFE_OR_MISSING_FILE:" + name)
    return path.read_bytes()


def build(case_path, output):
    case_path = Path(case_path)
    if case_path.is_symlink() or not case_path.is_file():
        refuse("UNSAFE_CASE_INPUT")
    case = validate(json_load_bytes(case_path.read_bytes()))
    root = Path(output)
    if root.exists():
        refuse("OUTPUT_MUST_NOT_EXIST")
    root.mkdir(parents=True)
    source = Path(__file__).read_bytes()
    case_bytes = canonical(case)
    source_sha = digest(case_bytes)
    decision = {
        "schema": "firstcash209/decision/v1",
        "case_sha256": source_sha,
        "case_id": case["case_id"],
        "status": "ENGINEERING_PREPARATION_ONLY",
        "buyer_collected_cad": None,
        "buyer_accepted_delivery": False,
        "complete_cost_profit_cad": None,
        "autonomous_discovery_verified": False,
        "commercial_release_authorized": False,
        "options": [{"id": o["id"], "status": o["verdict"],
                     "costs_known": all(v is not None for v in o["complete_costs_cad"].values())}
                    for o in case["options"]],
    }
    data = {
        "CASE.json": case_bytes,
        "DECISION.json": canonical(decision),
        "DECISION.html": make_html(case, source_sha),
    }
    manifest = {
        "schema": "firstcash209/manifest/v1",
        "generator_source_sha256": digest(source),
        "files": {name: digest(data[name]) for name in FILE_NAMES},
    }
    for name in FILE_NAMES:
        (root / name).write_bytes(data[name])
    (root / "MANIFEST.json").write_bytes(canonical(manifest))
    verify(root)
    return decision


def verify(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        refuse("UNSAFE_OR_MISSING_OUTPUT")
    manifest = json_load_bytes(checked_path(root, "MANIFEST.json"))
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "generator_source_sha256", "files"}:
        refuse("MANIFEST_FIELDS")
    if manifest["schema"] != "firstcash209/manifest/v1":
        refuse("MANIFEST_SCHEMA")
    if manifest["generator_source_sha256"] != digest(Path(__file__).read_bytes()):
        refuse("GENERATOR_SOURCE_CHANGED")
    if not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(FILE_NAMES):
        refuse("MANIFEST_FILE_SET")
    data = {}
    for name in FILE_NAMES:
        data[name] = checked_path(root, name)
        if manifest["files"][name] != digest(data[name]):
            refuse("OUTPUT_FILE_HASH_MISMATCH:" + name)
    case = validate(json_load_bytes(data["CASE.json"]))
    decision = json_load_bytes(data["DECISION.json"])
    if decision["case_sha256"] != digest(canonical(case)):
        refuse("CASE_SOURCE_MISMATCH")
    expected_html = make_html(case, decision["case_sha256"])
    if data["DECISION.html"] != expected_html:
        refuse("HTML_REPLAY_MISMATCH")
    if data["DECISION.json"] != canonical({
        "schema": "firstcash209/decision/v1",
        "case_sha256": decision["case_sha256"],
        "case_id": case["case_id"],
        "status": "ENGINEERING_PREPARATION_ONLY",
        "buyer_collected_cad": None,
        "buyer_accepted_delivery": False,
        "complete_cost_profit_cad": None,
        "autonomous_discovery_verified": False,
        "commercial_release_authorized": False,
        "options": [{"id": o["id"], "status": o["verdict"],
                     "costs_known": all(v is not None for v in o["complete_costs_cad"].values())}
                    for o in case["options"]],
    }):
        refuse("DECISION_REPLAY_MISMATCH")
    if expected_html.count(b'class="sheet" data-page=') != 10:
        refuse("PAGE_CONTRACT_FAILURE")
    return {"status": "OFFLINE_PROOF_VERIFIED", "case_sha256": decision["case_sha256"],
            "html_sha256": digest(expected_html), "pages": 10}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    b = subs.add_parser("build")
    b.add_argument("--case", required=True)
    b.add_argument("--output", required=True)
    v = subs.add_parser("verify")
    v.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(args.case, args.output) if args.command == "build" else verify(args.output)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (Refusal, OSError, KeyError, TypeError, OverflowError) as e:
        parser.exit(2, "FIRSTCASH209_REFUSAL: " + str(e) + "\n")


if __name__ == "__main__":
    main()
