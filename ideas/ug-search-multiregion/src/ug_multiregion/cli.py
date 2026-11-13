"""Command-line entry points."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

from .data import load_samples
from .experiment import run, write_results
from .models import make_model

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"


def _fake_dataset(root: Path) -> Path:
    records = []
    for index in range(3):
        image = Image.new("RGB", (128, 96), (20, 20, 20))
        draw = ImageDraw.Draw(image); draw.rectangle((10 + index * 8, 10, 40, 40), fill=(220, 20, 20))
        draw.ellipse((75, 45, 110, 80), fill=(20, 220, 20))
        name = f"fake-{index}.png"; image.save(root / name)
        records.append({"id": str(index), "image": name, "question": "Where are the two shapes?",
                        "answer": "mock", "category": "spatial", "boxes": [[10, 10, 40, 40], [75, 45, 110, 80]]})
    path = root / "fake.json"; path.write_text(json.dumps(records), encoding="utf-8"); return path


def parser(step: int) -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=f"Run UG-Search multi-region Step {step}")
    value.add_argument("--dataset", help="JSON, JSONL, CSV, or TSV annotation path")
    value.add_argument("--benchmark", choices=("vstar", "hrbench"), default="vstar")
    value.add_argument("--model", default=DEFAULT_MODEL)
    value.add_argument("--k", type=int, default=3)
    value.add_argument("--visual-crop-ratios", default="2", help="Comma-separated official UG-Search crop ratios")
    value.add_argument("--output", default=f"outputs/step{step}")
    value.add_argument("--limit", type=int)
    value.add_argument("--oracle-padding", type=float, default=0.25)
    value.add_argument("--max-new-tokens", type=int, default=128)
    value.add_argument("--dry-run", "--mock-model", action="store_true", dest="dry_run")
    if step == 1:
        value.add_argument("--min-gain", type=float, default=0.0)
        value.add_argument("--max-greedy-crops", type=int)
    return value


def main(step: int, argv: list[str] | None = None) -> None:
    args = parser(step).parse_args(argv)
    if args.k < 1:
        raise SystemExit("--k must be at least 1")
    ratios = [float(value) for value in args.visual_crop_ratios.split(",")]
    temporary = tempfile.TemporaryDirectory() if args.dry_run and not args.dataset else None
    dataset = args.dataset or str(_fake_dataset(Path(temporary.name))) if temporary else args.dataset
    if not dataset:
        raise SystemExit("--dataset is required unless --dry-run is used")
    samples = load_samples(dataset, args.benchmark, args.limit)
    model = make_model(args.model, args.dry_run, args.max_new_tokens)
    predictions = run(samples, model, ratios, args.k, step, args.oracle_padding,
                      getattr(args, "min_gain", 0.0), getattr(args, "max_greedy_crops", None))
    write_results(predictions, args.output)
    print(Path(args.output, "results.md").read_text(), end="")
    if temporary: temporary.cleanup()


def step0_main(argv: list[str] | None = None) -> None: main(0, argv)
def step1_main(argv: list[str] | None = None) -> None: main(1, argv)


def baseline_main(argv: list[str] | None = None) -> None:
    """Run the official command used for the paper's Qwen2.5-VL V* result."""
    parser = argparse.ArgumentParser(description="Reproduce official UG-Search V* Bench (86.9)")
    parser.add_argument("--output", default="outputs/ug-baseline")
    parser.add_argument("--limit", type=int, help="Optional smoke-test limit; omitted for the reported full benchmark")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2] / "third_party" / "ug-framework"
    command = ["accelerate", "launch", "--num_processes=1", "-m", "lmms_eval", "--model", "qwen2_5_vl",
               "--model_args", "pretrained=Qwen/Qwen2.5-VL-7B-Instruct,attn_implementation=flash_attention_2,ug_search=True,num_visual_crops=1,visual_crop_ratio=2",
               "--tasks", "vstar_bench", "--batch_size", "1", "--log_samples", "--log_samples_suffix", "qwen2_5_vl",
               "--output_path", args.output]
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "lmms-eval") + os.pathsep + env.get("PYTHONPATH", "")
    if args.dry_run:
        print(shlex.join(command))
        return
    os.chdir(root / "LLaVA-NeXT")
    os.execvpe(command[0], command, env)
