# SPDX-License-Identifier: Apache-2.0
"""Re-evaluate the frozen model within a 1,024-token confirmation envelope."""

import argparse
import json
from pathlib import Path

import torch

from curriculum import digest
import fit


def run(args):
    manifest = json.loads(args.extension.read_bytes())
    bindings = {
        'original_inference_source_sha256': digest(Path(fit.__file__)),
        'extension_source_sha256': digest(Path(__file__)),
        'held_freeze_sha256': digest(args.held_freeze),
        'briefs_sha256': digest(args.cases),
        'adapter_sha256': digest(args.adapter),
    }
    if any(manifest[key] != value for key, value in bindings.items()) or manifest['raised_limit'] != 1024:
        raise ValueError('Inference context correction differs from its scope')
    original = fit.pad

    def pad(sequences, tokenizer):
        width = max(map(len, sequences))
        if width <= 768:
            return original(sequences, tokenizer)
        if width > manifest['raised_limit']:
            raise ValueError('Confirmation exceeds the registered extended envelope')
        return {
            'input_ids': torch.tensor([row + [tokenizer.pad_token_id] * (width - len(row)) for row in sequences]),
            'attention_mask': torch.tensor([[1] * len(row) + [0] * (width - len(row)) for row in sequences]),
        }

    # The primary executable and fit registration remain unchanged.
    fit.pad = pad
    try:
        fit.score(args)
    finally:
        fit.pad = original


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('base', 'data', 'registration', 'cases', 'held-freeze', 'adapter', 'extension', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    run(parser.parse_args())
