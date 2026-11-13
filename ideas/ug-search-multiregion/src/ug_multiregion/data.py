"""Dataset normalization for V* Bench and HR-Bench exports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Sample:
    id: str
    image: Path
    question: str
    answer: str
    boxes: tuple[tuple[float, float, float, float], ...] = ()
    category: str = ""


def _records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".tsv", ".csv"}:
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream, delimiter="\t" if path.suffix.lower() == ".tsv" else ","))
    with path.open(encoding="utf-8") as stream:
        value = ([json.loads(line) for line in stream if line.strip()]
                 if path.suffix.lower() == ".jsonl" else json.load(stream))
    if isinstance(value, dict):
        for key in ("data", "samples", "questions", "annotations"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return value


def _value(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _boxes(value: Any) -> tuple[tuple[float, float, float, float], ...]:
    if not value:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return ()
    if isinstance(value, dict):
        value = value.get("boxes", list(value.values()))
    result = []
    for box in value:
        if isinstance(box, dict):
            if all(key in box for key in ("x", "y", "width", "height")):
                box = [box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]]
            else:
                box = [box.get(key) for key in ("x1", "y1", "x2", "y2")]
        if isinstance(box, (list, tuple)) and len(box) >= 4 and all(x is not None for x in box[:4]):
            result.append(tuple(float(x) for x in box[:4]))
    return tuple(result)


def load_samples(path: str | Path, benchmark: str, limit: int | None = None) -> list[Sample]:
    """Load common JSON/JSONL/CSV/TSV benchmark exports and select multi-object rows."""
    source = Path(path)
    base = source.parent
    samples = []
    for index, row in enumerate(_records(source)):
        category = str(_value(row, "category", "task", "question_type", "type")).lower()
        wanted = (benchmark == "vstar" and ("spatial" in category or "relative" in category)) or (
            benchmark == "hrbench" and ("fcp" in category or "cross" in category))
        if category and not wanted:
            continue
        image = Path(str(_value(row, "image", "image_path", "img", "filename")))
        if not image.is_absolute():
            image = base / image
        samples.append(Sample(
            id=str(_value(row, "id", "question_id", "index", default=index)),
            image=image,
            question=str(_value(row, "question", "query", "text")),
            answer=str(_value(row, "answer", "label", "gt_answer")),
            boxes=_boxes(_value(row, "boxes", "oracle_boxes", "gt_boxes", "bboxes", default=[])),
            category=category,
        ))
        if limit is not None and len(samples) >= limit:
            break
    if not samples:
        raise ValueError(f"No {benchmark} multi-object samples found in {source}")
    return samples
