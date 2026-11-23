"""Read pinned public Hugging Face model identities without downloading weights."""

import json
import re

HOSTS = frozenset({'huggingface.co'})
BASE = 'ggml-org/Qwen3.8-27B-GGUF'
ADAPTER = 'harness-hub/Qwen3.8-27B-super-adapter-GGUF'
BASE_FILE = 'Qwen3.8-27B-Q8_0.gguf'
ADAPTER_FILE = 'Qwen3.8-27B-super-adapter-lora-F16.gguf'
RECIPE = 'https://huggingface.co/blog/harness-adapters-at-scale'
RELEASE_DAY = '2026-11-20'
PUBLISHER = 'harness-hub'
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
REVISION = re.compile(r'[a-f0-9]{40}\Z')


def pinned_model(repository, revision, filename, label, transport):
    if not REVISION.fullmatch(revision):
        raise ValueError('Use an immutable public model revision')
    url = 'https://huggingface.co/api/models/' + repository + '/revision/' + revision + '?blobs=true'
    answer = transport(url, HOSTS)
    card = json.loads(answer['text'])
    license_id = (card.get('cardData') or {}).get('license')
    if (card.get('id') != repository or card.get('sha') != revision or card.get('private') is not False
            or card.get('gated') is not False or license_id != 'apache-2.0' or not SHA256.fullmatch(answer['sha256'])):
        raise ValueError('The public pinned model identity, access or license has not been confirmed')
    matching = [item for item in card['siblings'] if item['rfilename'] == filename]
    if len(matching) != 1 or not SHA256.fullmatch(matching[0].get('lfs', {}).get('sha256', '')):
        raise ValueError('Registered artifact is missing its public LFS digest')
    obj = matching[0]['lfs']
    if type(obj.get('size')) is not int or obj['size'] <= 0:
        raise ValueError('Missing published artifact size')
    return {'id': label, 'url': url, 'publisher': repository.split('/')[0], 'version': revision,
            'sha256': answer['sha256'], 'published_on': None, 'effective_on': RELEASE_DAY,
            'artifact': {'repository': repository, 'file': filename, 'revision': revision,
                         'sha256': obj['sha256'], 'bytes': obj['size'], 'license': 'Apache-2.0'},
            'evidence_location': f"{filename} · Apache-2.0 · {obj['size']} bytes · LFS SHA-256 {obj['sha256']}"}


def observe(baseline, version, transport):
    base = pinned_model(BASE, baseline, BASE_FILE, 'baseline', transport)
    adapter = pinned_model(ADAPTER, version, ADAPTER_FILE, 'adapter', transport)
    notes = transport(RECIPE, HOSTS)
    if (not SHA256.fullmatch(notes['sha256']) or 'november 20, 2026' not in notes['text'].casefold()
            or not all(word in notes['text'].casefold() for word in ('harness adapter', 'qwen3.8-27b'))):
        raise ValueError('The dated upstream release and model relationship remain unverified')
    return [base, adapter, {'id': 'recipe', 'url': RECIPE, 'publisher': PUBLISHER, 'version': RELEASE_DAY,
                           'sha256': notes['sha256'], 'published_on': RELEASE_DAY, 'effective_on': RELEASE_DAY,
                           'evidence_location': 'Dated release and upstream experimental recipe'}]
