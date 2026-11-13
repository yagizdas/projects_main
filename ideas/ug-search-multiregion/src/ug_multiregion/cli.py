"""Command-line entry points."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

from .data import load_samples
from .experiment import run, write_results
from .models import make_model

DEFAULT_MODEL = "OpenGVLab/InternVL2_5-8B"


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
    value.add_argument("--crop-sizes", default="0.5", help="Comma-separated image-relative side ratios")
    value.add_argument("--output", default=f"outputs/step{step}")
    value.add_argument("--limit", type=int)
    value.add_argument("--oracle-padding", type=float, default=0.25)
    value.add_argument("--max-new-tokens", type=int, default=32)
    value.add_argument("--dry-run", "--mock-model", action="store_true", dest="dry_run")
    if step == 1:
        value.add_argument("--min-gain", type=float, default=0.0)
        value.add_argument("--max-greedy-crops", type=int)
    return value


def main(step: int, argv: list[str] | None = None) -> None:
    args = parser(step).parse_args(argv)
    if args.k < 1:
        raise SystemExit("--k must be at least 1")
    sizes = [float(value) for value in args.crop_sizes.split(",")]
    temporary = tempfile.TemporaryDirectory() if args.dry_run and not args.dataset else None
    dataset = args.dataset or str(_fake_dataset(Path(temporary.name))) if temporary else args.dataset
    if not dataset:
        raise SystemExit("--dataset is required unless --dry-run is used")
    samples = load_samples(dataset, args.benchmark, args.limit)
    model = make_model(args.model, args.dry_run, args.max_new_tokens)
    predictions = run(samples, model, sizes, args.k, step, args.oracle_padding,
                      getattr(args, "min_gain", 0.0), getattr(args, "max_greedy_crops", None))
    write_results(predictions, args.output)
    print(Path(args.output, "results.md").read_text(), end="")
    if temporary: temporary.cleanup()


def step0_main(argv: list[str] | None = None) -> None: main(0, argv)
def step1_main(argv: list[str] | None = None) -> None: main(1, argv)
