#!/usr/bin/env python3
"""Reproduce published scores for exact, version-bound assessments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from stat import S_ISREG


MANIFEST = Path(__file__).with_name('SOURCES.json')
LEVEL_CASES = Path(__file__).with_name('LEVEL-EVIDENCE.json')
SCORED_FORM_TYPES = {'checkbox', 'dropdown', 'radiogroup'}


def read_verified(directory, source):
    name = Path(source['filename'])
    if name.name != str(name) or name.suffix != '.json':
        raise ValueError('Expected one named JSON input.')
    path = directory / name
    size = source['bytes']
    if type(size) is not int or not 0 < size <= 6_291_456:
        raise ValueError('Invalid qualified input size.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        file_stat = os.fstat(stream.fileno())
        if not S_ISREG(file_stat.st_mode) or file_stat.st_size != size:
            raise ValueError(f'{path.name} differs from the qualified original.')
        data = stream.read(size + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != source['sha256']:
        raise ValueError(f'{path.name} differs from the qualified original.')
    return json.loads(data)


def option_score(option):
    if type(option) is int:
        return option
    pieces = str(option).rsplit('-', 1)
    return int(pieces[-1]) if len(pieces) == 2 and pieces[-1].isdigit() else 0


def totals(form, answers, *, use_legacy_encoding=False):
    maximum = {'RS': 0, 'MS': 0}
    scores = {'RS': 0, 'MS': 0}
    seen = set()
    for page in form['pages']:
        for section in page.get('elements', []):
            for question in section.get('elements', []):
                if question['type'] not in SCORED_FORM_TYPES:
                    continue
                name = question['name']
                section_kind = section['name'].rsplit('-', 1)[-1]
                kind = name.rsplit('-', 1)[-1]
                if kind not in {'RS', 'MS', 'NS'}:
                    kind = section_kind
                if kind not in maximum:
                    continue
                if name in seen:
                    raise ValueError('Duplicate scored question.')
                seen.add(name)
                options = {choice['value']: option_score(choice['value']) for choice in question['choices']}
                multiple = question['type'] == 'checkbox'
                maximum[kind] += sum(options.values()) if multiple else max(options.values(), default=0)
                selected = answers.get(name)
                if selected is None:
                    continue
                if isinstance(selected, list) != multiple:
                    raise ValueError(f'Unexpected answer shape for {name}.')
                selected = selected if multiple else [selected]
                if len(set(selected)) != len(selected):
                    raise ValueError(f'Unsupported answer option for {name}.')
                if use_legacy_encoding:
                    scores[kind] += sum(option_score(option) for option in selected)
                    continue
                if any(option not in options for option in selected):
                    raise ValueError(f'Unsupported answer option for {name}.')
                scores[kind] += sum(options[option] for option in selected)
    return scores, maximum


def published_formula(scores, maximum):
    raw, mitigation = scores['RS'], scores['MS']
    applied_discount = 5 * mitigation >= 2 * maximum['MS']
    current = (85 * raw + 50) // 100 if applied_discount else raw
    level = next(n for n in range(1, 5) if 4 * current <= n * maximum['RS'])
    return {'raw_impact': raw, 'mitigation': mitigation, 'current': current, 'level': level}


def replay(directory, selected, *, level_study=False):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assessments = manifest['assessments']
    if level_study:
        assessments = json.loads(LEVEL_CASES.read_text(encoding='utf-8'))['assessments']
    forms = {}
    outcomes = {}
    for case, definition in assessments.items():
        if selected and case != selected:
            continue
        original = read_verified(directory, definition)
        version = original.get('version')
        if version != definition['version']:
            raise ValueError(f'Original version evidence differs for {case}.')
        if version not in forms:
            forms[version] = read_verified(directory, manifest['definitions'][version])
        # The level study includes an encoded choice beyond the tagged option list.
        # Its two published PDFs independently bind the archived scorer's totals.
        observed, maximum = totals(forms[version], original['data'], use_legacy_encoding=level_study)
        result = published_formula(observed, maximum)
        if result != definition['published_scores']:
            raise ValueError(f'Computed scores differ from the independently checked publication for {case}.')
        outcomes[case] = {'form_version': version, 'original_sha256': definition['sha256'],
                          'scored': result, 'risk_maximum': maximum['RS'],
                          'mitigation_maximum_per_phase': maximum['MS'] // 2}
    if not outcomes:
        raise ValueError('Unknown named case.')
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_directory', type=Path, help='Directory of the pinned public JSON inputs.')
    parser.add_argument('--case', help='Optional exact case name from the selected evidence manifest.')
    parser.add_argument('--level-study', action='store_true', help='Reproduce the three independently checked legacy impact-level cases.')
    args = parser.parse_args()
    try:
        result = replay(args.source_directory, args.case, level_study=args.level_study)
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
