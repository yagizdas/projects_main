"""Crop proposal and oracle-crop utilities."""

from __future__ import annotations

from dataclasses import dataclass
from PIL import Image


@dataclass(frozen=True)
class Crop:
    id: str
    box: tuple[int, int, int, int]
    image: Image.Image


def sliding_crops(image: Image.Image, sizes: list[float], overlap: float = 0.5) -> list[Crop]:
    width, height = image.size
    crops: list[Crop] = []
    seen = set()
    for ratio in sizes:
        if not 0 < ratio <= 1:
            raise ValueError("crop sizes must be ratios in (0, 1]")
        cw, ch = max(1, round(width * ratio)), max(1, round(height * ratio))
        sx, sy = max(1, round(cw * (1 - overlap))), max(1, round(ch * (1 - overlap)))
        xs = list(range(0, max(1, width - cw + 1), sx))
        ys = list(range(0, max(1, height - ch + 1), sy))
        xs.append(width - cw); ys.append(height - ch)
        for y in sorted(set(ys)):
            for x in sorted(set(xs)):
                box = (x, y, x + cw, y + ch)
                if box not in seen:
                    seen.add(box)
                    crops.append(Crop(f"crop-{len(crops):04d}", box, image.crop(box)))
    return crops


def oracle_crops(image: Image.Image, boxes: tuple[tuple[float, float, float, float], ...], padding: float) -> list[Crop]:
    width, height = image.size
    result = []
    for index, raw in enumerate(boxes):
        x1, y1, x2, y2 = raw
        if max(raw) <= 1.0:  # normalized xyxy
            x1, x2, y1, y2 = x1 * width, x2 * width, y1 * height, y2 * height
        dx, dy = (x2 - x1) * padding, (y2 - y1) * padding
        box = (max(0, int(x1 - dx)), max(0, int(y1 - dy)), min(width, int(x2 + dx)), min(height, int(y2 + dy)))
        if box[2] > box[0] and box[3] > box[1]:
            result.append(Crop(f"oracle-{index:04d}", box, image.crop(box)))
    return result
