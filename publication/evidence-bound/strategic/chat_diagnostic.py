"""Test native instruction formatting on eight public development pairs."""

import argparse
from pathlib import Path
from time import perf_counter

import torch

from game import DECISIONS
from learn import file_hash, logits, open_model, read_supervision, render, restore, write_json


@torch.inference_mode()
def run(model, tokenizer, weight, examples, training, style):
    correct = 0
    started = perf_counter()
    for index in range(0, len(examples), 4):
        group = examples[index:index + 4]
        texts = []
        for case, _ in group:
            messages = [
                {"role": "system", "content": "Analyze the zero-sum game. Return only the single decision letter."},
                {"role": "user", "content": render(case, style, training)},
            ]
            texts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "Decision:")
        inputs = tokenizer(texts, add_special_tokens=False, padding=True, return_tensors="pt")
        choices = logits(model, weight, inputs)
        predicted = (choices[:, 0] <= choices[:, 1]).tolist()
        correct += sum(DECISIONS[int(index)] == label for index, (_, label) in zip(predicted, group))
    return {"correct": correct, "sample_count": len(examples), "batched_wall_seconds": perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.data / "development.jsonl"
    examples = read_supervision(source)[:16]
    training = read_supervision(args.data / "train.jsonl")
    model, tokenizer, weights = open_model(args.base, 2)
    results = {}
    for arm in ("base", "adapted"):
        if arm == "adapted":
            restore(model, args.adapter)
        for method in ("direct", "retrieval", "verified-tool"):
            results[f"{arm}_{method}"] = run(model, tokenizer, weights, examples, training, method)
    write_json(args.output, {"schema": "frontier/strategic-chat-diagnostic-v1", "scope": "Development diagnostic",
                             "selection": "First eight pairs in the frozen 32-pair development split",
                             "checkpoint_unchanged": True, "confirmation_accessed": False,
                             "development_sha256": file_hash(source), "adapter_sha256": file_hash(args.adapter),
                             "results": results})


if __name__ == "__main__":
    main()
