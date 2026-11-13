"""Crop proposal and oracle-crop utilities."""

from __future__ import annotations

from dataclasses import dataclass
from PIL import Image

from .official import sliding_windows


@dataclass(frozen=True)
class Crop:
    id: str
    box: tuple[int, int, int, int]
    image: Image.Image


def sliding_crops(image: Image.Image, ratios: list[float]) -> list[Crop]:
    """Wrap the official implementation for one or more visual crop ratios."""
    crops, seen = [], set()
    for ratio in ratios:
        if ratio <= 1:
            raise ValueError("visual crop ratios must be greater than 1")
        for box, crop_image in sliding_windows(image, ratio):
            if box not in seen:
                seen.add(box)
                crops.append(Crop(f"crop-{len(crops):04d}", box, crop_image))
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
            result.append(Crop(f"oracle-{index:04d}", box, image.crop(box).resize(image.size, Image.Resampling.LANCZOS)))
    return result
