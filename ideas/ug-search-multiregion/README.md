# UG-Search multi-region experiments

This project measures whether uncertainty-guided visual search leaves headroom on questions that
refer to multiple objects, and evaluates a training-free greedy multi-crop selection rule. It follows
the scoring idea from the authors' [official UG framework](https://github.com/ExplainableML/ug-framework):
lower mean generated-token entropy indicates a more informative crop. Unlike the official top-1
UG-Search path, this harness also answers from top-k crops, all ground-truth object crops, or a
greedily selected set. Selected crop IDs, pixel boxes, and entropy are retained as possible future
proposal-head labels.

## Setup

Python 3.10+ is required. For the CPU mock and tests:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

For a real run, use a Linux machine with an approximately 24 GB CUDA GPU and install the model
dependencies (Flash Attention is optional but recommended when supported):

```bash
pip install -e '.[gpu]'
pip install flash-attn --no-build-isolation  # optional
```

The default is `OpenGVLab/InternVL2_5-8B`, the 8B model used in the UG-Search evaluation. Any
Hugging Face model supported by `AutoModelForImageTextToText` and `AutoProcessor` can instead be
passed with `--model`. Model weights download on the first run.

## Datasets

Download [V* Bench](https://huggingface.co/datasets/craigwu/vstar_bench) and
[HR-Bench](https://huggingface.co/datasets/DreamMr/HR-Bench) from Hugging Face, accepting any
dataset terms. Export annotations to JSON, JSONL, CSV, or TSV and ensure each row has:

* an image path in `image` or `image_path`, relative to the annotation file;
* `question`, `answer`, and `category`/`task` (`spatial` or `relative_position` for V*, `FCP` for HR-Bench);
* for the oracle comparison, one `boxes`/`oracle_boxes`/`gt_boxes` list containing an `xyxy` box
  around **each** mentioned object. Boxes may be pixel coordinates or normalized to `[0, 1]`.

Official benchmark releases do not consistently provide all mentioned-object boxes. The top-1,
top-k, and greedy settings still run without them, but the oracle row is omitted for such samples.
Accuracy is exact-match after case/whitespace normalization, so preserve the benchmark's canonical
short answers when exporting. CSV/TSV box values should be JSON arrays.

## Run

Step 0 compares UG top-1, joint top-k, and oracle crops:

```bash
ug-step0 --benchmark vstar --dataset /data/vstar.json --k 3 \
  --crop-sizes 0.33,0.5 --output outputs/vstar-step0
ug-step0 --benchmark hrbench --dataset /data/hrbench-8k.tsv --k 3 \
  --crop-sizes 0.25,0.5 --output outputs/hrbench-step0
```

Step 1 repeats those baselines and adds the greedy set. It begins with the lowest-entropy singleton,
tests every remaining crop jointly with the selected set, and stops when the best candidate does not
lower entropy (or at an optional cap):

```bash
ug-step1 --benchmark vstar --dataset /data/vstar.json --k 3 \
  --crop-sizes 0.33,0.5 --min-gain 0 --max-greedy-crops 6 \
  --output outputs/vstar-step1
```

`--crop-sizes` are image-relative width/height ratios and proposals use 50% overlap.
`--oracle-padding` controls fractional padding around object boxes. `results.md` is the requested
accuracy table, `results.json` is its machine-readable equivalent, and `predictions.jsonl` contains
per-sample answers and crop-selection logs.

Both commands have a CPU-only smoke mode. With no dataset it creates three temporary fake samples:

```bash
ug-step0 --dry-run --output outputs/smoke-step0
ug-step1 --dry-run --output outputs/smoke-step1
```
