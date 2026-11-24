#!/usr/bin/env python3
"""Replay authorized Git source history into an allowlisted bilingual Pages release."""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote

import build_research_site as site
import frontier_public_watch as watch
import frontier_member_value as member
import frontier_member_first as editions


INBOX_ANCHOR = '5db5637d42c0f675cc7689674d5db7ceb91930da'
EDITORIAL_ANCHOR = 'f42516b85cc293899bdca8245d11aa4528aa2189'
EDITORIAL_PATH = 'docs/research/' + site.POSSIBILITY_INPUT
LEDGER = 'atlas-ledger.json'
RELEASE = 'atlas-release.json'
LEDGER_LIMIT = 20_000_000
SHA = re.compile('[0-9a-f]{40}')
COMMIT_URL = f'https://github.com/{watch.REPOSITORY}/commit/'
RUNS_URL = f'https://github.com/{watch.REPOSITORY}/actions/workflows/research-pages.yml'
BRANCH = 'refs/remotes/origin/frontier-watch-public'


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def digest(value):
    return sha256(value).hexdigest()


def git(*args):
    return subprocess.check_output(('git', *args))


def stamp(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def history(ref, anchor, path, limit):
    # The pinned first-parent history is the append log. An absent or rewritten
    # prefix is a failure, never a request to silently rebuild from current rows.
    entries = git('log', '--first-parent', '--format=%H %cI', ref).decode().splitlines()
    shas = [row.split(' ', 1)[0] for row in entries]
    if anchor not in shas:
        raise ValueError(f'Pinned history anchor absent for {path}')
    changed = git('log', '--full-history', '--first-parent', '--format=%H', f'{anchor}..{ref}', '--', path)
    selected = {anchor, *changed.decode().splitlines()}
    for row in reversed(entries[:shas.index(anchor) + 1]):
        commit, when = row.split(' ', 1)
        if commit not in selected:
            continue
        blob = f'{commit}:{path}'
        probe = subprocess.run(('git', 'cat-file', '-s', blob), capture_output=True, check=False)
        raw = b''
        if probe.returncode == 0 and int(probe.stdout) <= limit:
            raw = git('cat-file', 'blob', blob)
        yield commit, stamp(when), raw


def source_with_retry(url, limit):
    for attempt in range(3):
        try:
            return watch.fetch(url, limit)
        except (URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in {408, 429, 500, 502, 503, 504}:
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError('Unreachable retry state')


def verified_metadata(item, observed, request):
    def capture(url, limit):
        nonlocal primary_sha256
        raw = request(url, limit)
        primary_sha256 = digest(raw)
        return raw

    primary_sha256 = None
    title, url, published = watch.evidence(item, capture)
    if date.fromisoformat(published) > date.fromisoformat(observed[:10]):
        raise ValueError('Source date is later than its intake receipt')
    return {'title': title, 'url': url, 'source_date': published, 'primary_sha256': primary_sha256}


def cached_metadata(ledger, identity, item, commit, observed):
    for saved in ledger.get(identity, []):
        if (saved.get('publisher_commit'), saved.get('observed_at'), saved.get('source_version')) != (commit, observed, item['ref']):
            continue
        if saved.get('decision') != item['decision']:
            continue
        if item['source'] == 'arxiv':
            expected = f'https://arxiv.org/abs/{item["ref"]}'
        else:
            expected = f'https://github.com/{watch.SOURCES[item["source"]]}/releases/tag/{quote(item["ref"], safe="")}'
        if saved.get('url') != expected or not watch.SHA256.fullmatch(saved.get('primary_sha256', '')):
            continue
        title, day = saved['title'], saved['source_date']
        if (not isinstance(title, str) or not 0 < len(title) <= 250
                or any(watch.category(c) in ('Cc', 'Cf', 'Cs') for c in title)
                or date.fromisoformat(day).isoformat() != day or day > observed[:10]):
            continue
        return {key: saved[key] for key in ('title', 'url', 'source_date', 'primary_sha256')}
    return None


def read_inbox_history(revisions, holds, request, cache=None):
    records, rejected, selected = {}, [], {}
    observed_commits = set()
    published_commits = {
        entry['publisher_commit'] for versions in (cache or {}).values() for entry in versions
        if isinstance(entry, dict) and isinstance(entry.get('publisher_commit'), str)
        and SHA.fullmatch(entry['publisher_commit'])
    }
    # Repeated canonical source versions, including cross-stream duplicates,
    # never create an additional entry. A new arXiv version is a revision.
    seen = set()
    for commit, observed, raw in revisions:
        observed_commits.add(commit)
        try:
            inbox = watch.parse_inbox(raw)
        except (ValueError, TypeError, RecursionError):
            rejected.append({'commit': commit, 'reason': 'invalid-inbox'})
            continue
        selected = inbox
        for stream, items in inbox.items():
            for identity, item in items.items():
                key = identity, item['ref']
                if key in seen or digest(identity.encode()) in holds:
                    continue
                try:
                    metadata = cached_metadata(cache or {}, identity, item, commit, observed)
                except (ValueError, KeyError, TypeError, AttributeError):
                    metadata = None
                if metadata is None:
                    try:
                        metadata = verified_metadata(item, observed, request)
                    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
                        rejected.append({'commit': commit, 'reason': type(error).__name__,
                                         'http': error.code if isinstance(error, HTTPError) else None})
                        continue
                seen.add(key)
                records.setdefault(identity, []).append({
                    **metadata, 'source': item['source'], 'source_version': item['ref'],
                    'publisher_commit': commit, 'observed_at': observed,
                    'stream': stream, 'decision': item['decision'],
                })
    if published_commits - observed_commits:
        raise ValueError('Previously published inbox history was removed')
    return records, selected, rejected


def editorial_history(revisions):
    records = {}
    for commit, observed, raw in revisions:
        for item in site.parse_possibilities(raw):
            versions = records.setdefault(item['id'], [])
            if not versions or versions[-1]['record'] != item:
                versions.append({'record': item, 'reviewed_commit': commit, 'observed_at': observed})
    return records


def source_identity(url):
    if url.startswith('https://arxiv.org/abs/'):
        key = url.rsplit('/', 1)[-1]
        if re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', key):
            return 'arxiv:' + key.split('v')[0]
    for source, repository in watch.SOURCES.items():
        prefix = f'https://github.com/{repository}/releases/tag/'
        if url.startswith(prefix):
            tag = unquote(url[len(prefix):])
            return f'{source}:{tag}'
    return None


def assemble(editorial, references):
    """Produce one entry per editorial ID or canonical public source."""
    common = {}
    entries = []
    for key, versions in editorial.items():
        item = versions[-1]['record']
        entry = {'id': 'shift-' + key, 'state': site.record_state(item), 'editorial': versions, 'sources': {}}
        entries.append(entry)
        for record in versions:
            for citation in record['record']['sources']:
                identity = source_identity(citation['url'])
                if identity is not None:
                    if identity in common and common[identity] is not entry:
                        raise ValueError('Duplicate reviewed Atlas source identity')
                    common[identity] = entry
    for identity, versions in references.items():
        if identity not in common:
            entry = {'id': 'watch-' + identity.replace(':', '-'), 'state': 'discovered',
                     'editorial': [], 'sources': {}}
            entries.append(entry)
        else:
            entry = common[identity]
        entry['sources'][identity] = versions

    def priority(entry):
        if entry['editorial']:
            last = entry['editorial'][-1]
            return last['record'].get('assessment', {}).get('priority', 2)
        return 3

    def freshness(entry):
        observations = [item['observed_at'] for item in entry['editorial']]
        observations.extend(item['observed_at'] for versions in entry['sources'].values() for item in versions)
        return max(observations)

    entries.sort(key=lambda entry: (-datetime.fromisoformat(freshness(entry)).timestamp(), entry['id']))
    entries.sort(key=priority)
    return {'schema': 'frontier-omega-alpha/atlas-ledger-v1', 'records': entries,
            'updated_at': max(freshness(entry) for entry in entries)}


def archive_links(entry, lang):
    old = entry['editorial'][:-1]
    sources = [row for versions in entry['sources'].values() for row in versions]
    if not old and len(sources) < (1 if entry['editorial'] else 2):
        return ''
    fr = lang == 'fr'
    output = []
    for record in reversed(old):
        item = record['record']
        local = item[lang]
        evidence = site.EVIDENCE_LABELS[item['evidence']][fr]
        output.append(f'<li><time datetime="{record["observed_at"]}">{record["observed_at"][:10]}</time>'
                      f' · {escape(evidence)} · {escape(local["title"])}. {escape(local["signal"])} '
                      f'<a href="{COMMIT_URL}{record["reviewed_commit"]}">{"Version examinée" if fr else "Reviewed revision"}</a></li>')
    for record in sorted(sources, key=lambda item: item['observed_at'], reverse=True):
        output.append(f'<li><time datetime="{record["observed_at"]}">{record["observed_at"][:10]}</time>'
                      f' · <a href="{escape(record["url"])}">{escape(record["source_version"])}</a>'
                      f' · <a href="{COMMIT_URL}{record["publisher_commit"]}">{"Reçu de veille" if fr else "Intake receipt"}</a></li>')
    label = 'Historique des preuves' if fr else 'Evidence history'
    return f'<details class="atlas-history"><summary>{label}</summary><ul>{"".join(output)}</ul></details>'


def reference_card(entry, lang, active):
    versions, = entry['sources'].values()
    last = max(versions, key=lambda item: (
        int(item['source_version'].rsplit('v', 1)[1]) if item['source'] == 'arxiv' else 0, item['observed_at']))
    first = versions[0]['observed_at']
    key = escape(entry['id'])
    fr = lang == 'fr'
    read, receipt = ('Source primaire', 'Reçu du registre') if fr else ('Primary source', 'Ledger receipt')
    if fr:
        status = 'Référence externe dont la version est confirmée. Les résultats demeurent à vérifier.'
        alternative = 'Meilleure solution de rechange à établir.'
        next_test = ('Reproduire un résultat annoncé sur des données autorisées, puis le comparer à la méthode de référence.'
                     if last['source'] == 'arxiv' else
                     'Comparer cette version à la précédente sur la même charge, avec des critères d’acceptation communs.')
        inactive = 'Cette référence est conservée dans l’historique de la veille.'
    else:
        status = 'External reference with a confirmed version. Its results await independent verification.'
        alternative = 'Strongest comparable alternative still to be established.'
        next_test = ('Reproduce one reported result on rights-cleared inputs and compare it with the strongest incumbent.'
                     if last['source'] == 'arxiv' else
                     'Compare this release and its predecessor on the same workload under shared acceptance criteria.')
        inactive = 'This reference is retained from an earlier watch selection.'
    label = watch.LABELS[lang][last['decision']]
    decision = label if (last['source'], last['source_version']) in active else inactive
    return (
        f'<article class="atlas-card" id="{key}" data-atlas-record data-state="discovered" aria-labelledby="{key}-title">'
        f'<div class="atlas-card-meta"><strong>{site.STATE_LABELS[lang]["discovered"]}</strong>'
        f'<time datetime="{first}">{first[:10]}</time></div>'
        f'<h3 id="{key}-title">{escape(last["title"])}</h3><p class="atlas-evidence">{status}</p>'
        f'<p>{decision} · {escape(last["source_version"])}</p>'
        f'<dl><div><dt>{"Comparaison" if fr else "Comparator"}</dt><dd>{alternative}</dd></div>'
        f'<div><dt>{"Prochaine étape" if fr else "Next step"}</dt><dd>{next_test}</dd></div></dl>'
        f'<ul class="atlas-links"><li><a href="{escape(last["url"])}">{read}</a></li>'
        f'<li><a href="{COMMIT_URL}{last["publisher_commit"]}">{receipt}</a></li></ul>'
        f'{archive_links(entry, lang)}</article>'
    )


def render(page, lang, ledger, selected, references, sealed_digest):
    available = {identity: {item['source_version']: item for item in versions}
                 for identity, versions in references.items()}
    current = {stream: [] for stream in watch.STREAMS}
    seen, active = set(), set()
    for stream, items in selected.items():
        for identity, item in items.items():
            row = available.get(identity, {}).get(item['ref'])
            if row is None or identity in seen:
                continue
            seen.add(identity)
            active.add((row['source'], row['source_version']))
            current[stream].append((row['title'], row['url'], row['source_date'], row['decision']))
    for rows in current.values():
        rows.sort(key=lambda row: (row[2], row[1]), reverse=True)

    entries = []
    for entry in ledger['records']:
        if entry['editorial']:
            latest = entry['editorial'][-1]['record']
            entries.append(site.possibility_card(latest, lang, archive_links(entry, lang)))
        else:
            entries.append(reference_card(entry, lang, active))
    records = f'<div class="atlas-grid" id="atlas-records" data-atlas-digest="{sealed_digest}">{"".join(entries)}</div>'
    fr = lang == 'fr'
    count = len(entries)
    label = f'{count} fiches publiques' if fr else f'{count} public records'
    freshness = 'Dernier ajout ou changement' if fr else 'Last content change'
    report = 'État de publication' if fr else 'Publication status'
    data = 'Registre et versions' if fr else 'Ledger and revisions'
    updated = ledger['updated_at']
    health = (f'<div class="atlas-health"><strong>{label}</strong><span>{freshness} '
              f'<time datetime="{updated}">{updated[:10]} · {updated[11:16]} UTC</time></span>'
              f'<a href="{LEDGER}">{data}</a><a href="{RELEASE}">{report}</a>'
              f'<a href="{RUNS_URL}">{"Historique des mises à jour" if fr else "Update history"}</a></div>')
    for marker, contents in ((site.POSSIBILITY_MARKER, records), (watch.MARKER, watch.render(current, lang)[0]),
                             ('<!-- FRONTIER_ATLAS_HEALTH -->', health)):
        if page.count(marker) != 1:
            raise ValueError('Unexpected release template')
        page = page.replace(marker, contents)
    return page


def same_deployment(release, previous):
    return release['projection_sha256'] == previous.get('projection_sha256')


def public_checkpoint(request):
    try:
        previous = json.loads(request(watch.SITE + RELEASE, 16_000))
        raw = request(watch.SITE + LEDGER, LEDGER_LIMIT)
        if digest(raw) != previous['ledger_sha256']:
            return {}, {}
        ledger = json.loads(raw)
        sources = {identity: rows for entry in ledger['records'] for identity, rows in entry['sources'].items()}
        return previous, sources
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return {}, {}


def prepare(output, revision, event, run, request=source_with_retry):
    previous, cache = public_checkpoint(request) if event != 'pull_request' else ({}, {})
    holds = watch.parse_holds(watch.HOLDS.read_bytes())
    references, selected, rejected = read_inbox_history(
        history(BRANCH, INBOX_ANCHOR, watch.INBOX_FILE, 4096), holds, request, cache)
    editorial = editorial_history(history(revision, EDITORIAL_ANCHOR, EDITORIAL_PATH, site.POSSIBILITY_MAX_BYTES))
    ledger = assemble(editorial, references)
    raw = canonical_json(ledger)
    if len(raw) > LEDGER_LIMIT:
        raise ValueError('Public ledger exceeds the supported single-file transfer limit')
    directory = output / 'frontier-omega-alpha'
    sealed = digest(raw)
    member_view, member_pages, member_digest = member.prepare(directory, ledger, sealed, run,
        previous.get('member_first'), lambda prior: editions.witnessed_run(prior, request),
        promote=event == 'schedule')
    for page, lang in watch.PAGES.items():
        source = Path(EDITORIAL_PATH).parent / page
        html = render(source.read_text(), lang, ledger, selected, references, sealed)
        for marker, contents in ((member.MARKER, member_pages[lang]),
                                 (member.PREVIEW_MARKER, member.home_preview(member_view, lang)),
                                 (member.PUBLIC_FEATURE_MARKER, member.public_feature(member_view, lang))):
            if html.count(marker) != 1:
                raise ValueError('Unexpected public member template')
            html = html.replace(marker, contents)
        (directory / page).write_text(html)
    (directory / LEDGER).write_bytes(raw)
    files = [(file.relative_to(output).as_posix(), digest(file.read_bytes()))
             for file in sorted(output.rglob('*')) if file.is_file()]
    preview = git('ls-tree', revision, 'products/alpha-genesis-harness/app',
                  'products/alpha-genesis-harness/scripts/publish_preview.py',
                  'products/alpha-genesis-harness/examples/customer-mission.json').decode()
    release = {'schema': 'frontier-omega-alpha/atlas-release-v1', 'source_commit': revision,
               'content_updated_at': ledger['updated_at'], 'ledger_sha256': sealed,
               'member_value_sha256': member_digest,
               'member_first': member_view['member_first'],
               'public_capability_sha256': {v['download']: v['sha256'] for v in member_view['capabilities'].values()},
               'records': len(ledger['records']), 'states': dict(Counter(row['state'] for row in ledger['records'])),
               'projection_sha256': digest(canonical_json([files, preview])),
               'workflow_run': run, 'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    release['decision_edition_sha256'] = {
        name.removeprefix('frontier-omega-alpha/'): fingerprint
        for name, fingerprint in files if name in site.DECISION_EDITION_ASSETS
    }
    accepted = [version for versions in references.values() for version in versions]
    if accepted:
        newest = max(accepted, key=lambda version: version['observed_at'])
        release['latest_accepted_reference'] = {key: newest[key] for key in ('publisher_commit', 'observed_at')}
    site.validate(output, staged=True)
    (directory / RELEASE).write_bytes(canonical_json(release))
    print(json.dumps({'inbox_head': git('rev-parse', BRANCH).decode().strip(), 'rejected': rejected,
                      'records': release['records'], 'states': release['states'], 'ledger_sha256': sealed}), file=sys.stderr)
    return release, not same_deployment(release, previous)


def verify_live(expected, revision, run, request=source_with_retry):
    release = json.loads(request(watch.SITE + RELEASE, 16_000))
    if release['ledger_sha256'] != expected or (revision and release['source_commit'] != revision):
        raise ValueError('Published source or ledger does not match the qualified projection')
    if run and release['workflow_run'] != run:
        raise ValueError('Published workflow run does not match')
    raw = request(watch.SITE + LEDGER, LEDGER_LIMIT)
    if digest(raw) != expected:
        raise ValueError('Live ledger bytes do not match')
    ledger = json.loads(raw)
    member_raw = request(watch.SITE + member.MEMBER_JSON, LEDGER_LIMIT)
    if digest(member_raw) != release['member_value_sha256']:
        raise ValueError('Live member evidence bytes do not match')
    member_evidence = json.loads(member_raw)
    if member_evidence['atlas_sha256'] != expected or member_evidence['publication'] != 'public-file':
        raise ValueError('Live member evidence does not bind the current public Atlas')
    sequenced = member_evidence['member_first']
    if sequenced != release['member_first']:
        raise ValueError('Member First sequencing receipt differs from the publication')
    for filename in (member.ENDPOINT_ZIP, member.ARCHIVE_ZIP):
        if digest(request(watch.SITE + filename, 500_000)) != release['public_capability_sha256'][filename]:
            raise ValueError('Live tool bytes do not match')
    editions = release['decision_edition_sha256']
    if set(editions) != {name.removeprefix('frontier-omega-alpha/') for name in site.DECISION_EDITION_ASSETS}:
        raise ValueError('Unexpected historical edition asset set')
    for name, fingerprint in editions.items():
        if digest(request(watch.SITE + name, 500_000)) != fingerprint:
            raise ValueError('Live historical edition bytes do not match')
    for path in ('', 'fr.html'):
        html = request(watch.SITE + path, LEDGER_LIMIT).decode()
        parser = site.Links()
        parser.feed(html)
        ids = {item['id'] for item in ledger['records']}
        if not ids.issubset(parser.ids) or ids & {'member', 'brief-content'}:
            raise ValueError('Live Atlas is missing one or more records')
        atlas = html.partition('id="possibility-shifts"')[2].partition('id="research"')[0]
        if f'data-atlas-digest="{expected}"' not in atlas or atlas.count('data-atlas-record') != len(ids):
            raise ValueError('Expected public records outside the wallet gate')
        entrance, _, reader = html.partition('<section id="member" class="frame workspace" hidden')
        workspace, _, preview = reader.partition('id="member-preview"')
        preview = preview.partition('id="possibility-shifts"')[0]
        if (not {'enter-club', 'member-preview', 'mf-quick-run'}.issubset(parser.ids)
                or 'id="access"' not in entrance or 'data-connect="token"' not in entrance
                or 'id="member-value"' not in workspace or 'id="mv-endpoint-run"' not in workspace
                or f'data-preview-count="{len(ids)}"' not in preview
                or any(marker in html for marker in (member.MARKER, member.PREVIEW_MARKER, '<!-- MV_SAMPLE -->'))):
            raise ValueError('Unpublished member-workbench rendering')
        edition = sequenced['edition']
        public = sequenced['public_feature']
        if (f'id="mf-edition" data-edition-run="{edition["member_run"]}"' not in workspace
                or 'id="mf-edition"' in atlas or bool(public) != ('id="atlas-editorial"' in atlas)
                or (public and f'id="atlas-editorial" data-public-run="{public["public_run"]}"' not in atlas)):
            raise ValueError('Member edition or public editorial placement does not match its release')
    release['live_checked_at_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    staging = commands.add_parser('stage')
    staging.add_argument('output', type=Path)
    staging.add_argument('event', choices=('schedule', 'push', 'pull_request', 'workflow_dispatch'))
    staging.add_argument('source_commit')
    staging.add_argument('workflow_run')
    live = commands.add_parser('verify')
    live.add_argument('ledger_sha256')
    live.add_argument('--source-commit', default='')
    live.add_argument('--workflow-run', default='')
    args = parser.parse_args()
    if args.command == 'stage':
        if not SHA.fullmatch(args.source_commit) or not args.workflow_run.isdecimal():
            parser.error('Missing exact deployment source or run')
        release, changed = prepare(args.output, args.source_commit, args.event, args.workflow_run)
        print(f'changed={str(changed).lower()}')
        print(f'ledger={release["ledger_sha256"]}')
    else:
        for attempt in range(6):
            try:
                print(json.dumps(verify_live(args.ledger_sha256, args.source_commit, args.workflow_run), sort_keys=True))
                return
            except (ValueError, KeyError, OSError) as error:
                if attempt == 5:
                    raise
                print(f'Waiting for matched live assets ({type(error).__name__})', file=sys.stderr)
                time.sleep(5)


if __name__ == '__main__':
    main()
