"""Train and replay a low-rank local causal model on strategic formalization."""

import argparse
from collections import Counter
from itertools import islice
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

from formalize import FIELDS, numeric_missing, ordinary_interpretation, read_jsonl, review_case, valid_case
from formalize import PRIOR, fingerprint

from learn import BASE_FILES, BASE_ID, BASE_REVISION, TARGETS
from learn import install, match_architecture, open_model, parameter_hash, peak_memory, restore, write_json


CODES = (" A", " B", " C", " D")
TASK = ("Read the brief for a two-state zero-sum game. Output exactly three letters, in order: timing, units, data.\n"
        "Timing A: purchase and policy public, rival fixes hidden state, private cue before row, no rival revision. "
        "B: cue after binding row. C: rival may respond to cue or realized row. D: insufficient timing or privacy.\n"
        "Units A: payoffs and fee share a unit. B: incompatible units with no conversion. C: units uncertain.\n"
        "Data A: numerical fee and both conditional accuracies given. B: fee missing. C: accuracies missing. D: both missing.\n")
METHOD = ("Determine what each player knows before each binding choice. Distinguish a declared policy "
          "from a realized row. Treat calibration as missing if either probability is unavailable. Use "
          "only explicit facts and never infer a common unit from the numerical values.\n")


def labels(oracle):
    return [options.index(oracle[key]) for key, options in FIELDS.items()]


def render(case, style, examples):
    prefix = TASK
    if style != "direct":
        prefix += METHOD
    if style == "retrieval":
        tokens = set(re.findall(r"\w+", case["brief"].casefold()))

        def distance(example):
            text = example["case"]
            overlap = len(tokens.intersection(re.findall(r"\w+", text["brief"].casefold())))
            return (case["lang"] != text["lang"], -overlap, text["id"])

        for row in islice(sorted(examples, key=distance), 2):
            prefix += "Practice brief: " + row["case"]["brief"] + "\nInterpretation:" + "".join(
                CODES[choice] for choice in labels(row["oracle"])) + "\n"
    return prefix + "Brief:\n" + case["brief"] + "\nInterpretation:"


def setup(base, threads):
    model, tokenizer, _ = open_model(base, threads)
    choices = [tokenizer.encode(code, add_special_tokens=False) for code in CODES]
    if not all(len(tokens) == 1 for tokens in choices):
        raise ValueError("Each interpretation code needs one native token")
    ids = [choice[0] for choice in choices]
    if len(set(ids)) != 4:
        raise ValueError("Interpretation codes must be distinct tokens")
    head = model.lm_head.weight[ids].detach().float()
    return model, tokenizer, ids, head


def model_batch(sequences, padding):
    length = max(map(len, sequences))
    return {"input_ids": torch.tensor([sequence + [padding] * (length - len(sequence)) for sequence in sequences]),
            "attention_mask": torch.tensor([[1] * len(sequence) + [0] * (length - len(sequence)) for sequence in sequences])}


def logits(model, head, sequences, positions, padding):
    hidden = model.model(**model_batch(sequences, padding), use_cache=False).last_hidden_state
    groups = torch.arange(len(sequences)).unsqueeze(1)
    return F.linear(hidden[groups, torch.as_tensor(positions)].float(), head)


def supervision(path):
    records = read_jsonl(path)
    for row in records:
        review_case(row["case"], row["oracle"])
    return records


def batches(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def batch_loss(model, tokenizer, ids, head, group):
    encoded = tokenizer([render(row["case"], "direct", ()) for row in group], add_special_tokens=False)["input_ids"]
    targets = [labels(row["oracle"]) for row in group]
    sequences = [prefix + [ids[choice] for choice in result[:-1]] for prefix, result in zip(encoded, targets)]
    positions = [[len(prefix) + offset - 1 for offset in range(3)] for prefix in encoded]
    scores = logits(model, head, sequences, positions, tokenizer.pad_token_id)
    allowed = torch.ones(3, 4, dtype=torch.bool)
    allowed[1, 3] = False
    value = F.cross_entropy(scores.masked_fill(~allowed, -torch.inf).reshape(-1, 4),
                            torch.tensor(targets).reshape(-1))
    return value, sum(map(len, sequences))


@torch.inference_mode()
def diagnostics(model, tokenizer, ids, head, rows, size):
    total = 0.0
    for group in batches(rows, size):
        loss, _ = batch_loss(model, tokenizer, ids, head, group)
        total += float(loss) * len(group)
    return total / len(rows)


def train(args):
    registration = json.loads(args.registration.read_text())
    plan = registration["training"]
    train_path, development_path = (args.data / f"{name}.jsonl" for name in ("train", "development"))
    for name, path in (("train", train_path), ("development", development_path)):
        if registration["data_sha256"][name] != fingerprint(path):
            raise ValueError(f"{name} inputs differ from the registered files")
    model, tokenizer, ids, head = setup(args.base, args.threads)
    training = supervision(train_path)
    development = supervision(development_path)
    torch.manual_seed(plan["seed"])
    parameters = install(model, plan["rank"], plan["alpha"], plan["tail_layers"])
    initial = {name: param.detach().clone() for name, param in parameters.items()}
    optimizer = torch.optim.AdamW(parameters.values(), lr=plan["learning_rate"], weight_decay=0.01)
    args.output.mkdir(parents=True)
    configuration = {
        "base_model_name_or_path": BASE_ID, "revision": BASE_REVISION, "peft_type": "LORA",
        "task_type": "CAUSAL_LM", "r": plan["rank"], "lora_alpha": plan["alpha"],
        "lora_dropout": 0.0, "bias": "none", "target_modules": list(TARGETS),
        "layers_to_transform": list(range(len(model.model.layers) - plan["tail_layers"], len(model.model.layers))),
        "layers_pattern": "layers", "inference_mode": True,
    }
    write_json(args.output / "adapter_config.json", configuration)
    size = plan["batch_size"]
    wall, cpu = perf_counter(), process_time()
    calibration_set = training[:size]
    audit = {"before": {
        "train_subset_loss": diagnostics(model, tokenizer, ids, head, calibration_set, size),
        "development_loss": diagnostics(model, tokenizer, ids, head, development, size)}}
    rng = random.Random(plan["seed"])
    order = list(training)
    steps = []
    for epoch in range(plan["epochs"]):
        rng.shuffle(order)
        for group in batches(order, size):
            optimizer.zero_grad(set_to_none=True)
            loss, tokens = batch_loss(model, tokenizer, ids, head, group)
            if not torch.isfinite(loss):
                raise ArithmeticError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters.values(), 1.0)
            optimizer.step()
            step = {"step": len(steps) + 1, "epoch": epoch + 1, "tokens": tokens, "loss": float(loss.detach())}
            steps.append(step)
            print(json.dumps(step), flush=True)
    audit["after"] = {
        "train_subset_loss": diagnostics(model, tokenizer, ids, head, calibration_set, size),
        "development_loss": diagnostics(model, tokenizer, ids, head, development, size)}
    trained = match_architecture(args.output / "adapter_model.safetensors", parameters, initial)
    report = {
        "schema": "frontier/strategic-formalizer-training-v1", "registration_sha256": fingerprint(args.registration),
        "source_sha256": {name: fingerprint(Path(__file__).with_name(name)) for name in ("fit.py", "formalize.py", "cases.py")},
        "base_model": BASE_ID, "base_revision": BASE_REVISION, "base_files_sha256": BASE_FILES,
        "base_dtype": "bfloat16", "adapter_dtype": "float32", "python": platform.python_version(),
        "torch": torch.__version__, "transformers": transformers.__version__, "platform": platform.platform(),
        "threads": args.threads, "train_cases": len(training), "development_cases": len(development),
        "loss_diagnostics": audit, "steps": steps, "initial_parameter_sha256": parameter_hash(initial),
        "checkpoint": trained, "cpu_seconds": process_time() - cpu, "wall_seconds": perf_counter() - wall,
        "peak_process_memory_bytes": peak_memory(),
    }
    write_json(args.output / "TRAINING-RESULT.json", report)


@torch.inference_mode()
def predict(model, tokenizer, ids, head, cases, style, examples, size):
    proposals = []
    for group in batches(cases, size):
        sequences = tokenizer([render(case, style, examples) for case in group], add_special_tokens=False)["input_ids"]
        selections = [dict() for _ in group]
        for field, options in FIELDS.items():
            scores = logits(model, head, sequences, [[len(sequence) - 1] for sequence in sequences],
                            tokenizer.pad_token_id)[:, 0, :len(options)]
            tokens = scores.argmax(dim=1).tolist()
            for proposal, sequence, index in zip(selections, sequences, tokens):
                proposal[field] = options[index]
                sequence.append(ids[index])
        proposals.extend(selections)
    return proposals


def score(args):
    examples = supervision(args.training)
    cases = [valid_case(case) for case in read_jsonl(args.cases)]
    if len({case["id"] for case in cases}) != len(cases) or not cases:
        raise ValueError("Expected distinct nonempty test inputs")
    model, tokenizer, ids, head = setup(args.base, args.threads)
    results, timing = {}, {}
    for plane in ("base", "adapted"):
        if plane == "adapted":
            if not args.adapter:
                break
            restore(model, args.adapter)
        for style in ("direct", "method", "retrieval"):
            start = perf_counter()
            proposal = predict(model, tokenizer, ids, head, cases, style, examples, args.batch_size)
            arm = f"{plane}_{style}"
            results[arm] = proposal
            timing[arm] = perf_counter() - start
            if style in ("method", "retrieval"):
                # The authorized numeric record exposes this part exactly.
                results[f"{arm}_with_numeric_tool"] = [
                    {**item, "missing": numeric_missing(case)} for case, item in zip(cases, proposal)]
    start = perf_counter()
    results["ordinary_rules_and_numeric_tool"] = [ordinary_interpretation(case) for case in cases]
    timing["ordinary_rules_and_numeric_tool"] = perf_counter() - start

    report = {
        "schema": "frontier/strategic-formalizer-predictions-v1", "case_sha256": fingerprint(args.cases),
        "training_sha256": fingerprint(args.training), "adapter_sha256": fingerprint(args.adapter) if args.adapter else None,
        "run_source_sha256": fingerprint(Path(__file__)), "base_weights_sha256": BASE_FILES["model.safetensors"],
        "elapsed_seconds": timing, "case_ids": [case["id"] for case in cases], "arms": results,
        "max_process_memory_bytes": peak_memory(), "lang_counts": dict(Counter(case["lang"] for case in cases)),
    }
    write_json(args.output, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="stage", required=True)
    trainer, scorer = subcommands.add_parser("train"), subcommands.add_parser("score")
    for sub in (trainer, scorer):
        sub.add_argument("--base", required=True, type=Path)
        sub.add_argument("--output", required=True, type=Path)
        sub.add_argument("--threads", default=3, type=int)
    trainer.add_argument("--data", type=Path, required=True)
    trainer.add_argument("--registration", type=Path, required=True)
    scorer.add_argument("--cases", type=Path, required=True)
    scorer.add_argument("--training", type=Path, required=True)
    scorer.add_argument("--adapter", type=Path)
    scorer.add_argument("--batch-size", default=8, type=int)
    args = parser.parse_args()
    if args.threads <= 0 or (args.stage == "score" and args.batch_size <= 0):
        parser.error("Use a positive thread and batch count")
    (train if args.stage == "train" else score)(args)


if __name__ == "__main__":
    main()
