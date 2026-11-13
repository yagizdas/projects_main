"""Step 0 baselines and Step 1 greedy set selection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from PIL import Image

from .crops import Crop, oracle_crops, sliding_crops
from .data import Sample
from .models import VisionLanguageModel


@dataclass
class Prediction:
    sample_id: str
    setting: str
    prediction: str
    answer: str
    correct: bool
    crop_ids: list[str]
    crop_boxes: list[tuple[int, int, int, int]]
    entropy: float | None


def _correct(prediction: str, answer: str) -> bool:
    clean = lambda text: " ".join(text.lower().strip().rstrip(".").split())
    return clean(prediction) == clean(answer)


def _predict(sample: Sample, image: Image.Image, setting: str, crops: list[Crop], entropy: float | None,
             model: VisionLanguageModel) -> Prediction:
    prediction = model.answer([image, *[crop.image for crop in crops]], sample.question)
    return Prediction(sample.id, setting, prediction, sample.answer, _correct(prediction, sample.answer),
                      [crop.id for crop in crops], [crop.box for crop in crops], entropy)


def greedy_select(crops: list[Crop], question: str, model: VisionLanguageModel, min_gain: float = 0.0,
                  max_crops: int | None = None, original: Image.Image | None = None) -> tuple[list[Crop], float]:
    """Select the best singleton, then add regions only while joint entropy falls."""
    if not crops:
        raise ValueError("No candidate crops")
    prefix = [original] if original is not None else []
    scored = [(model.entropy(prefix + [crop.image], question), crop) for crop in crops]
    entropy, first = min(scored, key=lambda item: item[0])
    selected, remaining = [first], [crop for crop in crops if crop.id != first.id]
    while remaining and (max_crops is None or len(selected) < max_crops):
        candidates = [(model.entropy(prefix + [c.image for c in selected] + [crop.image], question), crop)
                      for crop in remaining]
        next_entropy, crop = min(candidates, key=lambda item: item[0])
        if entropy - next_entropy <= min_gain:
            break
        selected.append(crop); remaining.remove(crop); entropy = next_entropy
    return selected, entropy


def run(samples: list[Sample], model: VisionLanguageModel, crop_sizes: list[float], k: int,
        step: int, oracle_padding: float = 0.25, min_gain: float = 0.0,
        max_greedy_crops: int | None = None) -> list[Prediction]:
    output = []
    for sample in samples:
        with Image.open(sample.image) as source:
            image = source.convert("RGB")
        crops = sliding_crops(image, crop_sizes)
        scored = sorted(((model.entropy([image, crop.image], sample.question), crop) for crop in crops), key=lambda x: x[0])
        output.append(_predict(sample, image, "ug_top1", [scored[0][1]], scored[0][0], model))
        topk = [crop for _, crop in scored[:k]]
        output.append(_predict(sample, image, f"ug_top{k}", topk, model.entropy([image, *[c.image for c in topk]], sample.question), model))
        oracle = oracle_crops(image, sample.boxes, oracle_padding)
        if oracle:
            output.append(_predict(sample, image, "oracle", oracle, model.entropy([image, *[c.image for c in oracle]], sample.question), model))
        if step == 1:
            selected, entropy = greedy_select(crops, sample.question, model, min_gain, max_greedy_crops, image)
            output.append(_predict(sample, image, "greedy", selected, entropy, model))
    return output


def write_results(predictions: list[Prediction], output_dir: str | Path) -> None:
    directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
    with (directory / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for prediction in predictions:
            stream.write(json.dumps(asdict(prediction)) + "\n")
    settings = sorted({p.setting for p in predictions})
    rows = []
    for setting in settings:
        values = [p for p in predictions if p.setting == setting]
        rows.append({"setting": setting, "correct": sum(p.correct for p in values), "total": len(values),
                     "accuracy": sum(p.correct for p in values) / len(values)})
    (directory / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    table = ["| setting | correct | total | accuracy |", "|---|---:|---:|---:|"]
    table += [f"| {r['setting']} | {r['correct']} | {r['total']} | {r['accuracy']:.4f} |" for r in rows]
    (directory / "results.md").write_text("\n".join(table) + "\n", encoding="utf-8")
