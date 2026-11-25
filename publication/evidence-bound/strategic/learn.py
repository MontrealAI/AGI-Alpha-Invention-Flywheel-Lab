"""Fit and compare a local causal language model on exact strategic decisions."""

import argparse
from hashlib import file_digest, sha256
import json
import math
from pathlib import Path
import platform
import random
import resource
from time import perf_counter, process_time

from safetensors import safe_open
from safetensors.torch import save_file
import torch
from torch import nn
from torch.nn import functional as F
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

from game import DECISIONS, Game, compare, digest_document, read_games


BASE_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
BASE_REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
BASE_FILES = {
    "config.json": "8eb740e8bbe4cff95ea7b4588d17a2432deb16e8075bc5828ff7ba9be94d982a",
    "tokenizer.json": "9ca9acddb6525a194ec8ac7a87f24fbba7232a9a15ffa1af0c1224fcd888e47c",
    "tokenizer_config.json": "4ec77d44f62efeb38d7e044a1db318f6a939438425312dfa333b8382dbad98df",
    "special_tokens_map.json": "2b7379f3ae813529281a5c602bc5a11c1d4e0a99107aaa597fe936c1e813ca52",
    "model.safetensors": "5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c",
}

TASK = ("Zero-sum measurement game. Your opponent sees your buy/skip choice and mixed policy, then picks "
        "one hidden payoff column. Each row gives your payoff in columns 0 then 1. Buying costs the fee "
        "and lets you choose your row after a noisy signal. Accuracy gives P(signal=column) by column in percent. "
        "Skipping chooses your row without the signal. Buy only if the best worst-case payoff after paying the fee "
        "strictly exceeds the best worst-case payoff of skipping. A means Buy and B means Skip.\n")
METHOD = ("To solve, list the vectors of payoffs across the two columns for each row if skipping. If buying, "
          "list every pair of signal-conditional rows. Weight each payoff by its signal probability in that "
          "column and subtract the fee once. In each list take the convex hull, maximizing the smaller "
          "coordinate. Check single points and interpolations where the coordinates are equal. In a tie skip.\n")
TARGETS = ("q_proj", "v_proj")
CHOICES = (" A", " B")


def file_hash(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def write_json(path, content):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(content, sort_keys=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def case_text(case):
    rows = "; ".join(f"({left},{right})" for left, right in case.payoffs)
    return f"Rows: {rows}. Accuracy: {case.accuracy[0]}%,{case.accuracy[1]}%. Fee: {case.fee}."


def read_supervision(path):
    examples = []
    for line in path.read_text(encoding="utf8").splitlines():
        observation = json.loads(line)
        game = Game.from_document(observation["input"])
        decision, bounds = compare(game)
        if (observation["input_sha256"] != digest_document(game.document()) or observation["label"] != decision
                or any(observation["exact"][action] != bounds[action].document() for action in DECISIONS)):
            raise ValueError(f"Unverified supervision: {game.id}")
        examples.append((game, decision))
    if not examples or len({game.id for game, _ in examples}) != len(examples):
        raise ValueError("Expected nonempty distinct examples")
    return examples


def _case_distance(case, other):
    return (10 * abs(len(case.payoffs) - len(other.payoffs))
            + abs(case.fee - other.fee)
            + sum(abs(x - y) for x, y in zip(case.accuracy, other.accuracy)) / 20
            + sum(abs(x - y) for r, s in zip(sorted(case.payoffs), sorted(other.payoffs))
                  for x, y in zip(r, s)) / 6)


def render(case, style="direct", examples=()):
    prefix = TASK
    if style in ("method", "retrieval", "verified-tool"):
        prefix += METHOD
    if style == "retrieval":
        nearest = sorted(examples, key=lambda record: (_case_distance(case, record[0]), record[0].id))[:2]
        prefix += "Worked decisions from separate games:\n"
        for game, label in nearest:
            prefix += f"{case_text(game)} Decision: {CHOICES[DECISIONS.index(label)].strip()}\n"
    if style == "verified-tool":
        _, values = compare(case)
        prefix += (f"Verified exact payoffs on this game are net buy {values['BUY'].value} "
                   f"and skip {values['SKIP'].value}. Use these bounds for the decision.\n")
    return prefix + case_text(case) + "\nDecision:"


class LowRankProjection(nn.Module):
    def __init__(self, linear, rank, alpha):
        super().__init__()
        self.linear = linear
        self.scale = alpha / rank
        self.a = nn.Parameter(torch.empty(rank, linear.in_features))
        self.b = nn.Parameter(torch.zeros(linear.out_features, rank))
        nn.init.kaiming_uniform_(self.a, a=math.sqrt(5))

    def forward(self, inputs):
        original = self.linear(inputs)
        residual = F.linear(F.linear(inputs, self.a.to(inputs.dtype)), self.b.to(inputs.dtype))
        return original + residual * self.scale


def install(model, rank, alpha, tail_layers):
    layers = model.model.layers
    if not 1 <= tail_layers <= len(layers) or not 1 <= rank <= 64 or not 1 <= alpha <= 128:
        raise ValueError("Adapter configuration outside the registered architecture")
    parameters = {}
    for index in range(len(layers) - tail_layers, len(layers)):
        attention = layers[index].self_attn
        for field in TARGETS:
            projection = LowRankProjection(getattr(attention, field), rank, alpha)
            setattr(attention, field, projection)
            prefix = f"base_model.model.model.layers.{index}.self_attn.{field}"
            parameters[prefix + ".lora_A.weight"] = projection.a
            parameters[prefix + ".lora_B.weight"] = projection.b
    return parameters


def open_model(base, threads):
    if {name: file_hash(base / name) for name in BASE_FILES} != BASE_FILES:
        raise ValueError("Base model or tokenizer bytes differ from the pinned source")
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True, trust_remote_code=False)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, trust_remote_code=False,
                                                use_safetensors=True, torch_dtype=torch.bfloat16,
                                                attn_implementation="sdpa")
    model.requires_grad_(False)
    model.eval()
    choices = [tokenizer.encode(choice, add_special_tokens=False) for choice in CHOICES]
    if not all(len(tokens) == 1 for tokens in choices) or choices[0] == choices[1]:
        raise ValueError("The two decisions must be distinguishable single tokens")
    weight = model.lm_head.weight[[tokens[0] for tokens in choices], :].detach().float()
    return model, tokenizer, weight


def logits(model, weight, batch):
    hidden = model.model(**batch, use_cache=False).last_hidden_state
    last = batch["attention_mask"].sum(dim=1) - 1
    return F.linear(hidden[torch.arange(len(last)), last].float(), weight)


def peak_memory():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if platform.system() == "Darwin" else peak * 1024


def parameter_hash(table):
    state = sha256()
    for name, param in sorted(table.items()):
        state.update(name.encode() + b"\x00" + param.detach().cpu().numpy().tobytes())
    return state.hexdigest()


def match_architecture(out, table, initial):
    current = {name: param.detach().clone().contiguous() for name, param in table.items()}
    temporary = out.with_suffix(".part")
    save_file(current, temporary, metadata={"format": "pt"})
    temporary.replace(out)
    change = sum(torch.count_nonzero(data != initial[name]).item() for name, data in current.items())
    after = parameter_hash(current)
    return {"sha256": file_hash(out), "parameter_sha256": after, "changed_parameters": change,
            "trainable_parameters": sum(param.numel() for param in current.values()), "bytes": out.stat().st_size}


@torch.inference_mode()
def collect(model, tokenizer, weight, games, style, examples, batch_size):
    results = []
    for i in range(0, len(games), batch_size):
        batch = games[i:i + batch_size]
        started = perf_counter()
        inputs = tokenizer([render(case, style, examples) for case in batch], padding=True, return_tensors="pt")
        token_counts = inputs["attention_mask"].sum(dim=1).tolist()
        probabilities = logits(model, weight, inputs).softmax(dim=1).tolist()
        elapsed = perf_counter() - started
        for game, choices, tokens in zip(batch, probabilities, token_counts):
            selected = DECISIONS[0] if choices[0] > choices[1] else DECISIONS[1]
            results.append({"id": game.id, "input_sha256": digest_document(game.document()),
                            "decision": selected, "probability_buy": choices[0], "tokens": tokens,
                            "batch_share_seconds": elapsed / len(batch)})
    return results


def train(args):
    path = args.data / "train.jsonl"
    model, tokenizer, weight = open_model(args.base, args.threads)
    examples = read_supervision(path)
    torch.manual_seed(args.seed)
    params = install(model, args.rank, args.alpha, args.tail_layers)
    initial = {name: parameter.detach().clone() for name, parameter in params.items()}
    adapter_config = {"base_model_name_or_path": BASE_ID, "revision": BASE_REVISION,
                      "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": args.rank, "lora_alpha": args.alpha,
                      "lora_dropout": 0.0, "bias": "none", "target_modules": list(TARGETS),
                      "layers_to_transform": list(range(len(model.model.layers) - args.tail_layers, len(model.model.layers))),
                      "layers_pattern": "layers", "inference_mode": True}
    report = {"schema": "frontier/strategic-llm-training-v1", "configuration": {
        "base_model": BASE_ID, "base_revision": BASE_REVISION, "base_files_sha256": BASE_FILES,
        "license": "Apache-2.0", "objective": "Two-token conditional causal-LM decision preference",
        "seed": args.seed, "epochs": args.epochs, "batch_size": args.batch_size,
        "learning_rate": args.learning_rate, "adapter": adapter_config, "training_file_sha256": file_hash(path),
        "training_count": len(examples), "validation_excluded_from_fit": True, "confirmation_excluded_from_fit": True,
        "base_dtype": "bfloat16", "trainable_dtype": "float32", "threads": args.threads,
        "python_version": platform.python_version(), "torch_version": torch.__version__,
        "transformers_version": transformers.__version__, "platform": platform.platform(),
        "calculation_source_sha256": {name: file_hash(Path(__file__).with_name(name)) for name in ("learn.py", "game.py")}},
        "initial_parameter_sha256": parameter_hash(initial), "steps": []}
    args.output.mkdir(parents=True)
    write_json(args.output / "adapter_config.json", adapter_config)
    write_json(args.output / "TRAINING-PLAN.json", report)
    optimizer = torch.optim.AdamW(params.values(), lr=args.learning_rate, weight_decay=0.01)
    index = list(range(len(examples)))
    rng = random.Random(args.seed)
    cpu, wall = process_time(), perf_counter()
    step = 0
    for epoch in range(args.epochs):
        rng.shuffle(index)
        for begin in range(0, len(index), args.batch_size):
            group = [examples[i] for i in index[begin:begin + args.batch_size]]
            inputs = tokenizer([render(case) for case, _ in group], padding=True, return_tensors="pt")
            targets = torch.tensor([DECISIONS.index(label) for _, label in group], dtype=torch.long)
            optimizer.zero_grad(set_to_none=True)
            predicted = logits(model, weight, inputs)
            loss = F.cross_entropy(predicted, targets)
            if not torch.isfinite(loss):
                raise ArithmeticError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params.values(), max_norm=1.0)
            optimizer.step()
            step += 1
            row = {"step": step, "epoch": epoch + 1, "cross_entropy": float(loss.detach()),
                   "batch_tokens": int(inputs["attention_mask"].sum()), "elapsed_seconds": perf_counter() - wall}
            report["steps"].append(row)
            print(json.dumps(row), flush=True)
            if step % 10 == 0:
                match_architecture(args.output / "latest-work-in-progress.safetensors", params, initial)
                write_json(args.output / "TRAINING-PROGRESS.json", report)
    report["actual_step_count"] = step
    report["training_wall_seconds"] = perf_counter() - wall
    report["training_cpu_seconds"] = process_time() - cpu
    report["peak_process_memory_bytes"] = peak_memory()
    report["adapter_result"] = match_architecture(args.output / "adapter_model.safetensors", params, initial)
    write_json(args.output / "TRAINING-RESULT.json", report)


def restore(model, path):
    configuration = json.loads(path.with_name("adapter_config.json").read_text())
    if configuration["base_model_name_or_path"] != BASE_ID or configuration["revision"] != BASE_REVISION:
        raise ValueError("Adapter has a different pinned base")
    parameters = install(model, configuration["r"], configuration["lora_alpha"], len(configuration["layers_to_transform"]))
    with safe_open(path, framework="pt", device="cpu") as archive:
        if set(archive.keys()) != set(parameters):
            raise ValueError("Adapter weights do not match the registered layer mapping")
        with torch.no_grad():
            for name, parameter in parameters.items():
                loaded = archive.get_tensor(name)
                if loaded.shape != parameter.shape or loaded.dtype != parameter.dtype or not torch.isfinite(loaded).all():
                    raise ValueError("Invalid adapter tensor")
                parameter.copy_(loaded)


def score(args):
    models = read_games(args.cases)
    examples = read_supervision(args.training) if args.training else ()
    model, tokenizer, weight = open_model(args.base, args.threads)
    styles = ["direct", "method"]
    if examples:
        styles.append("retrieval")
    if args.verified_tools:
        styles.append("verified-tool")
    before = perf_counter()
    results = {}
    for style in styles:
        results["base_" + style] = collect(model, tokenizer, weight, models, style, examples, args.batch_size)
    if args.adapter:
        restore(model, args.adapter)
        for style in styles:
            results["adapted_" + style] = collect(model, tokenizer, weight, models, style, examples, args.batch_size)
    report = {"schema": "frontier/strategic-llm-score-v1", "model_id": BASE_ID, "model_revision": BASE_REVISION,
              "weights_sha256": BASE_FILES["model.safetensors"], "adapter_sha256": file_hash(args.adapter) if args.adapter else None,
              "case_bytes_sha256": file_hash(args.cases), "training_example_sha256": file_hash(args.training) if args.training else None,
              "prediction_source_sha256": file_hash(Path(__file__)), "case_count": len(models),
              "wall_seconds": perf_counter() - before, "peak_process_memory_bytes": peak_memory(), "arms": results}
    write_json(args.output, report)


def main():
    command = argparse.ArgumentParser(description=__doc__)
    sub = command.add_subparsers(dest="command", required=True)
    learner, evaluator = sub.add_parser("train"), sub.add_parser("score")
    for parser in (learner, evaluator):
        parser.add_argument("--base", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("--batch-size", type=int, default=8)
    learner.add_argument("--data", type=Path, required=True)
    learner.add_argument("--epochs", type=int, default=2)
    learner.add_argument("--rank", type=int, default=8)
    learner.add_argument("--alpha", type=int, default=16)
    learner.add_argument("--tail-layers", type=int, default=8)
    learner.add_argument("--learning-rate", type=float, default=0.002)
    learner.add_argument("--seed", type=int, default=710162)
    evaluator.add_argument("--cases", type=Path, required=True)
    evaluator.add_argument("--adapter", type=Path)
    evaluator.add_argument("--training", type=Path)
    evaluator.add_argument("--verified-tools", action="store_true")
    args = command.parse_args()
    if args.threads < 1 or args.batch_size < 1:
        command.error("Use a positive CPU thread and batch count")
    if args.command == "train":
        if args.epochs < 1 or not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
            command.error("Expected positive number of epochs and learning rate")
        train(args)
    else:
        score(args)


if __name__ == "__main__":
    main()
