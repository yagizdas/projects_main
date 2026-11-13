from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from ug_multiregion.cli import main
from ug_multiregion.crops import Crop
from ug_multiregion.experiment import greedy_select


class SetModel:
    def entropy(self, images, question):
        return {1: 0.8, 2: 0.4, 3: 0.5}[len(images)]


def test_greedy_stops_when_an_added_crop_has_no_gain():
    image = Image.new("RGB", (2, 2))
    crops = [Crop(str(i), (0, 0, 2, 2), image) for i in range(3)]
    selected, entropy = greedy_select(crops, "q", SetModel())
    assert len(selected) == 2
    assert entropy == 0.4


def test_both_dry_run_commands_end_to_end(tmp_path: Path):
    for step in (0, 1):
        output = tmp_path / f"step{step}"
        main(step, ["--dry-run", "--output", str(output), "--k", "2", "--crop-sizes", "0.5,0.75"])
        rows = json.loads((output / "results.json").read_text())
        settings = {row["setting"] for row in rows}
        assert {"ug_top1", "ug_top2", "oracle"} <= settings
        assert ("greedy" in settings) == (step == 1)
        predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
        assert all(item["crop_ids"] and item["crop_boxes"] for item in predictions)
