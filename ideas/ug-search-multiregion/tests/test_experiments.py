from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from ug_multiregion.cli import baseline_main, main
from ug_multiregion.crops import Crop
from ug_multiregion.experiment import greedy_select
from ug_multiregion.prepare import normalize_record, write_dataset


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
        main(step, ["--dry-run", "--output", str(output), "--k", "2", "--visual-crop-ratios", "2,3"])
        rows = json.loads((output / "results.json").read_text())
        settings = {row["setting"] for row in rows}
        assert {"ug_top1", "ug_top2", "oracle"} <= settings
        assert ("greedy" in settings) == (step == 1)
        predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
        assert all(item["crop_ids"] and item["crop_boxes"] for item in predictions)


def test_baseline_dry_run_uses_official_paper_setup(capsys):
    baseline_main(["--dry-run"])
    command = capsys.readouterr().out
    assert "Qwen/Qwen2.5-VL-7B-Instruct" in command
    assert "ug_search=True,num_visual_crops=1,visual_crop_ratio=2" in command
    assert "--tasks vstar_bench" in command


def test_prepare_data_parses_tiny_fixture(tmp_path: Path):
    fixture = {"question_id": "q1", "text": "Where are both objects?", "label": "B",
               "category": "relative_position", "bbox_target": [[1, 2, 3, 4], [10, 20, 5, 6]],
               "target_object": ["cup", "plate"], "image": Image.new("RGB", (32, 32))}
    parsed = normalize_record(fixture, "vstar", "test", 0)
    assert parsed["boxes"] == [[1.0, 2.0, 4.0, 6.0], [10.0, 20.0, 15.0, 26.0]]
    records = write_dataset([fixture], "vstar", "test", tmp_path)
    assert records[0]["target_objects"] == ["cup", "plate"]
    assert (tmp_path / "vstar" / records[0]["image"]).is_file()


def test_hrbench_never_emits_oracle_results(tmp_path: Path):
    dataset = tmp_path / "hr.json"
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 32)).save(image)
    dataset.write_text(json.dumps([{"id": "h1", "image": image.name, "question": "Compare both items",
                                    "answer": "mock", "category": "cross-instance",
                                    "boxes": [[0, 0, 5, 5], [10, 10, 20, 20]]}]))
    output = tmp_path / "output"
    main(0, ["--dry-run", "--benchmark", "hrbench", "--dataset", str(dataset), "--output", str(output)])
    assert "oracle" not in {row["setting"] for row in json.loads((output / "results.json").read_text())}
