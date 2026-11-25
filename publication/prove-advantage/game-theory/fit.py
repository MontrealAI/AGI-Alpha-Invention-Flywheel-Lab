# SPDX-License-Identifier: Apache-2.0
"""Fit and evaluate a compact evidence-pointer adapter on local model weights."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import random
import re
import sys
from time import perf_counter, process_time

import torch
from torch.nn import functional as F
import transformers

from curriculum import ACCESS, digest, read_cases, read_training, write_json

RETAINED_LOADER = Path(__file__).resolve().parents[2] / 'evidence-bound' / 'strategic'
sys.path.insert(0, str(RETAINED_LOADER))
from learn import (BASE_FILES, BASE_ID, BASE_REVISION, TARGETS, install, logits,
                   match_architecture, open_model, parameter_hash, peak_memory, restore)


TASK = ('For the named actor making the named choice, does access to the named datum follow from the rules? '
        'Use known for certain possession or logically implied access in every applicable situation at or before '
        'the choice. Use hidden for unambiguous denial or access only after that choice. '
        'Use unclear for missing, conditional, or conflicting access. Give the number of one decisive rule. '
        'Use 0 only for an unclear result due to the absence of a decisive rule. '
        'Read the actual actor and choice: a different person, later choice, or similar datum proves nothing.')
REPLY = '\nDecisive rule:'


def sections(case, query, guidance=False):
    rules = [f'{i}. {rule}' for i, rule in enumerate(case['rules'], 1)]
    subject = '\n'.join(rules)
    subject += f'\nActor: {query["observer"]}\nChoice: {query["decision"]}\nDatum: {query["datum"]}'
    if guidance:
        cited_terms = set(words(f'{query["observer"]} {query["datum"]}'))
        scores = [len(cited_terms.intersection(words(rule))) for rule in case['rules']]
        hit_count = max(scores)
        if hit_count:
            numbers = ', '.join(str(i) for i, score in enumerate(scores, 1) if score == hit_count)
            subject += f'\nAn exact word-overlap lookup suggests inspecting rule numbers {numbers}; inspect all rules.'
    return subject


def prompt(tokenizer, case, query, examples=(), guidance=False):
    text = TASK
    for item in examples:
        example = item['case']
        answer, = item['oracle']
        text += '\n\nWorked example:\n' + sections(example, example['queries'][0])
        text += '\nAccess: ' + answer['access'] + REPLY + str(answer['witness'][0])
    text += '\n\nRules to assess:\n' + sections(case, query, guidance)
    return tokenizer.apply_chat_template([{'role': 'user', 'content': text}], tokenize=True,
                                         add_generation_prompt=True) + tokenizer.encode('Access:', add_special_tokens=False)


def words(text):
    return re.findall(r'\w+', text.casefold())


def lookup(case, query, train):
    target = set(words(sections(case, query)))
    def relevance(item):
        sample = item['case']
        example = set(words(sections(sample, sample['queries'][0])))
        return (sample['language'] != case['language'], -len(target & example), sample['id'])
    matches = sorted(train, key=relevance)
    first = matches[0]
    second = next(item for item in matches if item['case']['language'] == case['language']
                  and item['oracle'][0]['access'] != first['oracle'][0]['access'])
    return [first, second]


def pieces(tokenizer):
    def one(text):
        tokens = tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) != 1:
            raise ValueError('A registered output token is not from the pinned tokenizer')
        return tokens[0]
    return ([one(' ' + label) for label in ACCESS], [one(str(i)) for i in range(9)],
            tokenizer.encode(REPLY, add_special_tokens=False))


def groups(records, size):
    for offset in range(0, len(records), size):
        yield records[offset:offset + size]


def pad(sequences, tokenizer):
    width = max(map(len, sequences))
    if width > 768:
        raise ValueError('Transcript exceeds registered context')
    return {
        'input_ids': torch.tensor([row + [tokenizer.pad_token_id] * (width - len(row)) for row in sequences]),
        'attention_mask': torch.tensor([[1] * len(row) + [0] * (width - len(row)) for row in sequences]),
    }


def prepared(items, tokenizer, access_ids, separator):
    rows = []
    for item in items:
        case = item['case']
        for query, answer in zip(case['queries'], item['oracle'], strict=True):
            prefix = prompt(tokenizer, case, query)
            label = ACCESS.index(answer['access'])
            prefix_with_label = prefix + [access_ids[label]] + separator
            rows.append((prefix_with_label, len(prefix) - 1, label, answer['witness'][0], len(case['rules'])))
    return rows


def batch_loss(model, tokenizer, batch, weight):
    snippets = [row[0] for row in batch]
    inputs = pad(snippets, tokenizer)
    hidden = model.model(**inputs, use_cache=False).last_hidden_state
    row_indices = torch.arange(len(batch))
    at_access = hidden[row_indices, [row[1] for row in batch]]
    at_rule = hidden[row_indices, [len(row[0]) - 1 for row in batch]]
    access_scores = F.linear(at_access.float(), weight[:len(ACCESS)])
    witness_scores = F.linear(at_rule.float(), weight[len(ACCESS):])
    allowed = (torch.arange(9).unsqueeze(0) <= torch.tensor([row[4] for row in batch]).unsqueeze(1))
    allowed[:, 0] = torch.tensor([row[2] == ACCESS.index('unclear') for row in batch])
    witness_scores = witness_scores.masked_fill(~allowed, -torch.inf)
    access_loss = F.cross_entropy(access_scores, torch.tensor([row[2] for row in batch]))
    witness_loss = F.cross_entropy(witness_scores, torch.tensor([row[3] for row in batch]))
    return access_loss, witness_loss, int(inputs['attention_mask'].sum())


@torch.inference_mode()
def loss_report(model, tokenizer, rows, batch_size, weight):
    totals = Counter()
    for group in groups(rows, batch_size):
        classification, pointer, _ = batch_loss(model, tokenizer, group, weight)
        totals['access'] += float(classification) * len(group)
        totals['witness'] += float(pointer) * len(group)
    return {key: score / len(rows) for key, score in totals.items()}


def registration(args):
    record = json.loads(args.registration.read_bytes())
    for source, expected in record['code_sha256'].items():
        if digest(Path(__file__).with_name(source)) != expected:
            raise ValueError('Study source differs from registration: ' + source)
    if digest(RETAINED_LOADER / 'learn.py') != record['loader_sha256']:
        raise ValueError('Retained model loader differs from registration')
    for split, expected in record['data_sha256'].items():
        if digest(args.data / (split + '.json')) != expected:
            raise ValueError('Study data differs from registration: ' + split)
    return record


def token_weights(model, access_ids, witness_ids):
    return model.lm_head.weight[access_ids + witness_ids].detach().float()


def fit(args):
    spec = registration(args)
    plan = spec['fit']
    train = read_training(args.data / 'train.json')
    development = read_training(args.data / 'development.json')
    if {tuple(item['case']['rules']) for item in train} & {tuple(item['case']['rules']) for item in development}:
        raise ValueError('Training and development rules overlap')
    model, tokenizer, _ = open_model(args.base, plan['threads'])
    access_ids, witness_ids, separator = pieces(tokenizer)
    weight = token_weights(model, access_ids, witness_ids)
    train = prepared(train, tokenizer, access_ids, separator)
    development = prepared(development, tokenizer, access_ids, separator)
    torch.manual_seed(plan['seed'])
    parameters = install(model, plan['rank'], plan['alpha'], plan['tail_layers'])
    initial = {name: parameter.detach().clone() for name, parameter in parameters.items()}
    optimizer = torch.optim.AdamW(parameters.values(), lr=plan['learning_rate'])
    args.output.mkdir(parents=True)
    adapter_config = {
        'base_model_name_or_path': BASE_ID, 'revision': BASE_REVISION, 'peft_type': 'LORA',
        'task_type': 'CAUSAL_LM', 'r': plan['rank'], 'lora_alpha': plan['alpha'], 'lora_dropout': 0.0,
        'bias': 'none', 'target_modules': list(TARGETS), 'layers_pattern': 'layers', 'inference_mode': True,
        'layers_to_transform': list(range(len(model.model.layers) - plan['tail_layers'], len(model.model.layers))),
    }
    write_json(args.output / 'adapter_config.json', adapter_config)
    start, compute = perf_counter(), process_time()
    batch_size = plan['batch_size']
    before = loss_report(model, tokenizer, development, batch_size, weight)
    randomizer = random.Random(plan['seed'])
    steps = []
    for epoch in range(plan['epochs']):
        randomizer.shuffle(train)
        for group in groups(train, batch_size):
            optimizer.zero_grad(set_to_none=True)
            access_loss, witness_loss, tokens = batch_loss(model, tokenizer, group, weight)
            loss = (access_loss + witness_loss) / 2
            if not torch.isfinite(loss):
                raise ArithmeticError('Nonfinite fit loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters.values(), 1.0)
            optimizer.step()
            row = {'update': len(steps) + 1, 'epoch': epoch + 1, 'tokens': tokens,
                   'access_loss': float(access_loss.detach()), 'witness_loss': float(witness_loss.detach())}
            print(json.dumps(row), flush=True)
            steps.append(row)
    after = loss_report(model, tokenizer, development, batch_size, weight)
    checkpoint = match_architecture(args.output / 'adapter_model.safetensors', parameters, initial)
    receipt = {
        'schema': 'frontier/strategic-evidence-pointer-fit/v1', 'base': BASE_ID, 'base_revision': BASE_REVISION,
        'base_files_sha256': BASE_FILES, 'base_dtype': 'bfloat16', 'base_trainable': False,
        'registration_sha256': digest(args.registration), 'initial_parameter_sha256': parameter_hash(initial),
        'checkpoint': checkpoint, 'train_queries': len(train), 'development_queries': len(development),
        'updates': len(steps), 'model_train_tokens': sum(row['tokens'] for row in steps),
        'supervised_tokens': len(train) * plan['epochs'] * 2, 'development_before': before,
        'development_after': after, 'wall_seconds': perf_counter() - start, 'cpu_seconds': process_time() - compute,
        'peak_memory_bytes': peak_memory(), 'python': platform.python_version(),
        'torch': torch.__version__, 'transformers': transformers.__version__,
    }
    write_json(args.output / 'TRAINING-RECEIPT.json', receipt)


@torch.inference_mode()
def predict(model, tokenizer, cases, train, arm, batch_size, pieces_):
    access_ids, witness_ids, separator = pieces_
    weight = token_weights(model, access_ids, witness_ids)
    result = {case['id']: [] for case in cases}
    rows = [(case, query) for case in cases for query in case['queries']]
    tokens = 0
    for group in groups(rows, batch_size):
        prefixes = [prompt(tokenizer, case, query, lookup(case, query, train) if arm == 'base_retrieval' else (),
                           guidance=arm == 'base_word_lookup') for case, query in group]
        padded = pad(prefixes, tokenizer)
        first = logits(model, weight[:len(ACCESS)], padded).softmax(dim=1)
        indices = first.argmax(dim=1).tolist()
        pointer_contexts = [prefix + [access_ids[index]] + separator for prefix, index in zip(prefixes, indices)]
        padded_pointer = pad(pointer_contexts, tokenizer)
        pointers = logits(model, weight[len(ACCESS):], padded_pointer)
        for i, ((case, _), index) in enumerate(zip(group, indices)):
            numbers = range(0 if ACCESS[index] == 'unclear' else 1, len(case['rules']) + 1)
            score = pointers[i, list(numbers)].softmax(dim=0)
            witness = numbers[int(score.argmax())]
            result[case['id']].append({
                'access': ACCESS[index], 'witness': witness, 'access_options': first[i].tolist(),
                'witness_probability': float(score.max()),
            })
        tokens += int(padded['attention_mask'].sum() + padded_pointer['attention_mask'].sum())
    return result, tokens


def score(args):
    spec = registration(args)
    held = json.loads(args.held_freeze.read_bytes())
    if held['held_cases_sha256'] != digest(args.cases):
        raise ValueError('Held briefs differ from the frozen panel')
    if held['fit_sha256'] != digest(args.adapter.parent / 'TRAINING-RECEIPT.json'):
        raise ValueError('Fit receipt differs from the freeze')
    training_receipt = json.loads((args.adapter.parent / 'TRAINING-RECEIPT.json').read_bytes())
    if training_receipt['checkpoint']['sha256'] != digest(args.adapter):
        raise ValueError('Candidate adapter differs from the frozen training receipt')
    if training_receipt['registration_sha256'] != digest(args.registration):
        raise ValueError('Wrong training registration in fit receipt')
    cases = read_cases(args.cases)
    train = read_training(args.data / 'train.json')
    training_rules = {tuple(item['case']['rules']) for item in train}
    if any(tuple(case['rules']) in training_rules for case in cases):
        raise ValueError('A held case matches a training ruleset')
    plan = spec['fit']
    model, tokenizer, _ = open_model(args.base, plan['threads'])
    arms = {}
    pieces_ = pieces(tokenizer)
    for arm in ('base_direct', 'base_retrieval', 'base_word_lookup', 'adapted_direct'):
        if arm == 'adapted_direct':
            restore(model, args.adapter)
        start, compute = perf_counter(), process_time()
        predictions, tokens = predict(model, tokenizer, cases, train, arm, plan['batch_size'], pieces_)
        arms[arm] = {'predictions': predictions, 'wall_seconds': perf_counter() - start,
                     'cpu_seconds': process_time() - compute, 'model_forward_tokens': tokens}
    write_json(args.output, {
        'schema': 'frontier/strategic-observation-predictions/v1', 'cases_sha256': digest(args.cases),
        'held_freeze_sha256': digest(args.held_freeze), 'adapter_sha256': digest(args.adapter),
        'registration_sha256': digest(args.registration), 'peak_memory_bytes': peak_memory(), 'arms': arms,
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='stage', required=True)
    training = subcommands.add_parser('train')
    scoring = subcommands.add_parser('score')
    for command in (training, scoring):
        for name in ('base', 'data', 'registration', 'output'):
            command.add_argument('--' + name, type=Path, required=True)
    for name in ('cases', 'adapter', 'held-freeze'):
        scoring.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    (fit if args.stage == 'train' else score)(args)
