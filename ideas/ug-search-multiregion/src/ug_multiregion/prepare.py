"""Download Hugging Face benchmarks into the harness' portable JSON format."""

from __future__ import annotations

import argparse
import base64
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from PIL import Image


DATASETS = {
    # This community export restores V* Bench's original human annotations.  The
    # lmms-eval mirror deliberately omits target names and ground-truth boxes.
    "vstar": ("jae-minkim/vstar-bench-bbox-final", None, ("test",)),
    "hrbench": ("DreamMr/HR-Bench", "hrbench_version_split", ("hrbench_4k", "hrbench_8k")),
}


def _image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value
    if isinstance(value, Mapping):
        if value.get("bytes"):
            return Image.open(io.BytesIO(value["bytes"]))
        if value.get("path"):
            return Image.open(value["path"])
    if isinstance(value, str):
        return Image.open(io.BytesIO(base64.b64decode(value.strip('"'))))
    raise ValueError(f"Unsupported image value: {type(value).__name__}")


def normalize_record(row: Mapping[str, Any], benchmark: str, split: str, index: int) -> dict[str, Any]:
    """Normalize one HF row. Kept separate so parsing can be tested without network."""
    record: dict[str, Any] = {
        "id": str(row.get("question_id", row.get("index", index))),
        "question": str(row.get("text", row.get("question", ""))),
        "answer": str(row.get("label", row.get("answer", ""))),
        "category": str(row.get("category", "")),
        "split": split,
    }
    if benchmark == "vstar":
        # The source V* annotation format is xywh; our loader consumes xyxy.
        boxes = row.get("bbox_target") or []
        record["boxes"] = [[float(x), float(y), float(x) + float(w), float(y) + float(h)]
                           for x, y, w, h in boxes]
        record["target_objects"] = list(row.get("target_object") or [])
    else:
        record["options"] = [str(row[key]) for key in "ABCD" if row.get(key) is not None]
        record["boxes"] = []
        record["target_objects"] = []
    return record


def write_dataset(rows: Iterable[Mapping[str, Any]], benchmark: str, split: str,
                  root: Path, limit: int | None = None) -> list[dict[str, Any]]:
    images = root / benchmark / "images"
    images.mkdir(parents=True, exist_ok=True)
    records = []
    for index, row in enumerate(rows):
        if limit is not None and index >= limit:
            break
        record = normalize_record(row, benchmark, split, index)
        filename = f"{split}-{record['id']}-{index}.jpg"
        with _image(row["image"]) as source:
            source.convert("RGB").save(images / filename, quality=95)
        record["image"] = f"images/{filename}"
        records.append(record)
    return records


def prepare(root: str | Path, benchmarks: Iterable[str], limit: int | None = None) -> None:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("prepare-data requires the 'data' extra: pip install -e '.[data]'") from exc
    destination = Path(root)
    for benchmark in benchmarks:
        repo, config, splits = DATASETS[benchmark]
        # Pilot/fixture runs stream so --limit does not first materialize multi-GB
        # image parquet files. Full preparation uses the durable HF cache.
        dataset = load_dataset(repo, config, streaming=limit is not None)
        records = []
        for split in splits:
            remaining = None if limit is None else max(limit - len(records), 0)
            if remaining == 0:
                break
            records.extend(write_dataset(dataset[split], benchmark, split, destination, remaining))
        output = destination / benchmark / "annotations.json"
        output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(f"{benchmark}: wrote {len(records)} samples to {output}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Prepare V* Bench and HR-Bench from Hugging Face")
    parser.add_argument("--output", default="data")
    parser.add_argument("--benchmark", action="append", choices=tuple(DATASETS), dest="benchmarks")
    parser.add_argument("--limit", type=int, help="Testing/pilot limit per benchmark")
    args = parser.parse_args(argv)
    prepare(args.output, args.benchmarks or DATASETS.keys(), args.limit)
