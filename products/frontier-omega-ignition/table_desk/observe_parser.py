"""Run the optional, pinned TD01 document parser on the two registered crops."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import resource
import tempfile
import time

HERE = Path(__file__).resolve().parent
PROMPT = "</s><s><predict_bbox><predict_classes><output_markdown><predict_text_in_pic>"
CROP_IDENTITIES = [
    "c044d33d4e29b3481165ad4ee987c18a6eee5a43a5ccc5882fe49b7d21583d19",
    "c6d79dcb776a8a9ac919ce1e300db94e96b958098ec0a5d7dbded7e5f06e1e0b",
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--crops", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pin = json.loads((HERE / "parser-model.json").read_text())
    os.environ["HF_HUB_OFFLINE"] = "1"
    clock, cpu = time.monotonic(), time.process_time()
    receipt = {"model": pin["repository"], "revision": pin["revision"],
               "model_sha256": pin["sha256"]["model.safetensors"], "device": "cpu",
               "dtype": "float32", "prompt": PROMPT, "max_new_tokens": 2048,
               "do_sample": False, "num_beams": 1, "repetition_penalty": 1.1, "crops": []}
    try:
        import torch
        from PIL import Image
        from transformers import AutoModel, AutoProcessor, GenerationConfig
        torch.set_num_threads(4)
        receipt["threads"] = torch.get_num_threads()
        receipt["versions"] = {name: version(name) for name in
                               ("torch", "torchvision", "transformers", "timm", "pillow", "tokenizers")}
        with tempfile.TemporaryDirectory(prefix="td01-") as temp:
            # Only verified provider files enter the directory used for model loading.
            model = Path(temp) / "nemotron_35_parse"
            model.mkdir()
            for name, expected in pin["sha256"].items():
                src = (args.model / name).resolve(strict=True)
                if digest(src) != expected:
                    raise ValueError(f"Model file mismatch: {name}")
                (model / name).symlink_to(src)
            start = time.monotonic()
            processor = AutoProcessor.from_pretrained(model, local_files_only=True, trust_remote_code=True)
            net = AutoModel.from_pretrained(model, local_files_only=True, trust_remote_code=True,
                                            dtype=torch.float32).to("cpu").eval()
            config = GenerationConfig.from_pretrained(model, local_files_only=True)
            config.max_new_tokens = 2048
            config.num_beams = 1
            config.do_sample = False
            config.repetition_penalty = 1.1
            receipt["load_wall_seconds"] = round(time.monotonic() - start, 4)
            for page, expected in enumerate(CROP_IDENTITIES, 1):
                source = args.crops / f"page-{page}.png"
                if digest(source) != expected:
                    raise ValueError(f"Unregistered crop {page}")
                start, cpu_start = time.monotonic(), time.process_time()
                with Image.open(source) as pic:
                    inputs = processor(images=[pic.convert("RGB")], text=PROMPT,
                                       return_tensors="pt", add_special_tokens=False)
                with torch.inference_mode():
                    ids = net.generate(**inputs, generation_config=config)
                output = args.output / f"page-{page}.txt"
                output.write_text(processor.batch_decode(ids, skip_special_tokens=False)[0], encoding="utf-8")
                receipt["crops"].append({"page": page, "image_sha256": expected,
                    "raw_sha256": digest(output), "returned_ids": ids.shape[-1],
                    "input_ids": inputs["input_ids"].shape[-1],
                    "wall_seconds": round(time.monotonic()-start, 4),
                    "cpu_seconds": round(time.process_time()-cpu_start, 4)})
                dump(args.output / "observation.json", receipt)
        receipt["status"] = "completed"
    except Exception as error:
        receipt["status"] = "failed"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        receipt.update(wall_seconds=round(time.monotonic()-clock,4),
                       cpu_seconds=round(time.process_time()-cpu,4),
                       linux_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        dump(args.output / "observation.json", receipt)


if __name__ == "__main__":
    main()
