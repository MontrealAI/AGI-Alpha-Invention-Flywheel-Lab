# SPDX-License-Identifier: Apache-2.0
"""One CPU LoRA fit and comparison using free-form structured completions."""

import argparse
import json
from pathlib import Path
import platform
import random
import re
from time import perf_counter, process_time

import torch
import torch.nn.functional as F
import transformers

from protocols import PRIOR, TASK, compact, fingerprint, single_case, validate
from learn import BASE_FILES, BASE_ID, BASE_REVISION, TARGETS, install, match_architecture, open_model
from learn import parameter_hash, peak_memory, restore, write_json


def read_json(path):
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate JSON keys")
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def supervised(path):
    rows = read_json(path)
    for row in rows:
        single_case(row["case"])
        validate(row["record"])
    if not rows or len({row["case"]["id"] for row in rows}) != len(rows):
        raise ValueError("Supervision must contain distinct briefs")
    return rows


def render(case, tokenizer, examples=()):
    text = TASK
    for row in examples:
        text += "\nWorked brief: " + row["case"]["brief"] + "\nRecord: " + compact(row["record"])
    text += "\nBrief:\n" + case["brief"]
    return tokenizer.apply_chat_template([{"role": "user", "content": text}], tokenize=True,
                                         add_generation_prompt=True)


def batches(records, size):
    for start in range(0, len(records), size):
        yield records[start:start + size]


def completion_loss(model, tokenizer, rows):
    sequences, targets = [], []
    for row in rows:
        prefix = render(row["case"], tokenizer)
        completion = tokenizer.encode(compact(row["record"]), add_special_tokens=False) + [tokenizer.eos_token_id]
        sequences.append(prefix + completion)
        targets.append([-100] * len(prefix) + completion)
    length = max(map(len, sequences))
    if length > 768:
        raise ValueError("Fit transcript exceeds the registered token envelope")
    input_ids = torch.tensor([s + [tokenizer.pad_token_id] * (length - len(s)) for s in sequences])
    attention = torch.tensor([[1] * len(s) + [0] * (length - len(s)) for s in sequences])
    labels = torch.tensor([label + [-100] * (length - len(label)) for label in targets])[:, 1:]
    selected = labels != -100
    hidden = model.model(input_ids=input_ids, attention_mask=attention, use_cache=False).last_hidden_state
    scores = model.lm_head(hidden[:, :-1][selected]).float()
    return F.cross_entropy(scores, labels[selected]), int(attention.sum()), int(selected.sum())


@torch.inference_mode()
def loss_report(model, tokenizer, rows, size):
    losses = [completion_loss(model, tokenizer, group) for group in batches(rows, size)]
    return sum(float(loss) * tokens for loss, _, tokens in losses) / sum(tokens for _, _, tokens in losses)


def fit(args):
    experiment = read_json(args.registration)
    for name in ["train", "development"]:
        if experiment["data_sha256"][name] != fingerprint(args.data / (name + ".json")):
            raise ValueError("Training or development inputs differ from registration")
    for name, expected in experiment["source_sha256"].items():
        if fingerprint(Path(__file__).with_name(name)) != expected:
            raise ValueError("Executable source differs from registration: " + name)
    train = supervised(args.data / "train.json")
    dev = supervised(args.data / "development.json")
    if {row["case"]["brief"] for row in train} & {row["case"]["brief"] for row in dev}:
        raise ValueError("Training and development text overlap")
    plan = experiment["fit"]
    model, tokenizer, _ = open_model(args.base, plan["threads"])
    torch.manual_seed(plan["seed"])
    params = install(model, plan["rank"], plan["alpha"], plan["tail_layers"])
    initial = {name: tensor.detach().clone() for name, tensor in params.items()}
    optimizer = torch.optim.AdamW(params.values(), lr=plan["learning_rate"])
    args.output.mkdir(parents=True)
    config = {"base_model_name_or_path": BASE_ID, "revision": BASE_REVISION, "peft_type": "LORA",
              "task_type": "CAUSAL_LM", "r": plan["rank"], "lora_alpha": plan["alpha"], "lora_dropout": 0.0,
              "bias": "none", "target_modules": list(TARGETS), "layers_pattern": "layers", "inference_mode": True,
              "layers_to_transform": list(range(len(model.model.layers) - plan["tail_layers"], len(model.model.layers)))}
    write_json(args.output / "adapter_config.json", config)
    seed = random.Random(plan["seed"])
    size = plan["batch_size"]
    start, cpu = perf_counter(), process_time()
    before = loss_report(model, tokenizer, dev, size)
    steps = []
    for epoch in range(plan["epochs"]):
        seed.shuffle(train)
        for group in batches(train, size):
            optimizer.zero_grad(set_to_none=True)
            loss, tokens, target_tokens = completion_loss(model, tokenizer, group)
            if not torch.isfinite(loss):
                raise ArithmeticError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params.values(), 1.0)
            optimizer.step()
            step = {"update": len(steps) + 1, "epoch": epoch + 1, "loss": float(loss.detach()),
                    "input_and_target_tokens": tokens, "target_tokens": target_tokens}
            print(compact(step), flush=True)
            steps.append(step)
    after = loss_report(model, tokenizer, dev, size)
    checkpoint = match_architecture(args.output / "adapter_model.safetensors", params, initial)
    write_json(args.output / "TRAINING-RESULT.json", {
        "schema": "frontier/strategic-protocol-model-fit/v1", "base": BASE_ID,
        "base_revision": BASE_REVISION, "base_files_sha256": BASE_FILES, "base_dtype": "bfloat16",
        "adapter_dtype": "float32", "base_requires_grad": False,
        "registration_sha256": fingerprint(args.registration), "source_sha256": experiment["source_sha256"],
        "initial_parameter_sha256": parameter_hash(initial), "checkpoint": checkpoint,
        "train_cases": len(train), "development_cases": len(dev), "updates": len(steps),
        "final_step": steps[-1], "first_step": steps[0],
        "total_train_tokens": sum(step["input_and_target_tokens"] for step in steps),
        "total_supervised_tokens": sum(step["target_tokens"] for step in steps),
        "development_loss_before": before, "development_loss_after": after,
        "wall_seconds": perf_counter() - start, "cpu_seconds": process_time() - cpu,
        "peak_memory_bytes": peak_memory(), "python": platform.python_version(),
        "torch": torch.__version__, "transformers": transformers.__version__,
    })


def retrieve(case, rows):
    tokens = set(re.findall(r"\w+", case["brief"].casefold()))
    def distance(row):
        source = row["case"]
        overlap = len(tokens.intersection(re.findall(r"\w+", source["brief"].casefold())))
        return (source["lang"] != case["lang"], source["family"] != case["family"], -overlap, source["id"])
    return sorted(rows, key=distance)[:2]


@torch.inference_mode()
def predict(model, tokenizer, cases, examples):
    rows = []
    for case in cases:
        prompt = render(case, tokenizer, retrieve(case, examples) if examples else ())
        ids = torch.tensor([prompt])
        result = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=96, do_sample=False,
                                pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
        raw = tokenizer.decode(result[0, len(prompt):], skip_special_tokens=True).strip()
        clean = raw
        if clean.startswith("```json") and clean.endswith("```"):
            clean = clean[7:-3].strip()
        try:
            pairs = lambda items: dict(items) if len(dict(items)) == len(items) else None
            record = validate(json.loads(clean, object_pairs_hook=pairs))
        except ValueError:
            record = None
        rows.append({"id": case["id"], "record": record, "completion": raw})
    return rows


def score(args):
    registration = read_json(args.registration)
    if fingerprint(args.cases) not in (registration["held_input_sha256"], registration["data_sha256"]["development"]):
        raise ValueError("Case source outside frozen held and development cases")
    cases = [single_case(case.get("case", case)) for case in read_json(args.cases)]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Expected distinct case IDs")
    if fingerprint(args.data / "train.json") != registration["data_sha256"]["train"]:
        raise ValueError("Retrieval source does not match registered training cases")
    train = supervised(args.data / "train.json")
    if {row["case"]["brief"] for row in train} & {case["brief"] for case in cases}:
        raise ValueError("Retrieval examples overlap scoring text")
    model, tokenizer, _ = open_model(args.base, registration["fit"]["threads"])
    arms, elapsed = {}, {}
    for arm in ("base_direct", "base_retrieval", "adapted_direct"):
        if arm == "adapted_direct":
            restore(model, args.adapter)
        start = perf_counter()
        arms[arm] = predict(model, tokenizer, cases, train if arm == "base_retrieval" else ())
        elapsed[arm] = perf_counter() - start
    write_json(args.output, {
        "schema": "frontier/strategic-protocol-model-inference/v1", "cases_sha256": fingerprint(args.cases),
        "training_sha256": fingerprint(args.data / "train.json"), "adapter_sha256": fingerprint(args.adapter),
        "fit_source_sha256": fingerprint(Path(__file__)), "base_weights_sha256": BASE_FILES["model.safetensors"],
        "arms": arms, "wall_seconds": elapsed,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="stage", required=True)
    train = subcommands.add_parser("train")
    scoring = subcommands.add_parser("score")
    for command in (train, scoring):
        for option in ("base", "data", "registration", "output"):
            command.add_argument("--" + option, type=Path, required=True)
    scoring.add_argument("--cases", type=Path, required=True)
    scoring.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()
    (fit if args.stage == "train" else score)(args)


if __name__ == "__main__":
    main()
