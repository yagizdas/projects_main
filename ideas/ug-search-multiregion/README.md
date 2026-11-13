# UG-Search multi-region experiments

This harness tests multi-region extensions to UG-Search. It is grounded in the authors' official
[UG framework](https://github.com/ExplainableML/ug-framework), pinned as a Git submodule at
`third_party/ug-framework` (commit `13050ee49865e4330519108f42d1ccfccff1aee1`).

## What is official and what is ours

**Vendored, unchanged official code:** the complete UG framework submodule; specifically, the
Qwen2.5-VL UG-Search sliding-window proposal statements and normalized next-token entropy hook in
`lmms-eval/lmms_eval/models/qwen2_5_vl.py`. `ug_multiregion.official` is a thin adapter which loads
those statements directly from the pinned source. It deliberately does not copy or reimplement the
algorithm. `ug-baseline` invokes the vendored `lmms_eval` implementation itself.

**Our experimental code:** the Step 0/Step 1 CLIs, dataset normalization, oracle-box crops, top-k and
greedy multi-crop selection, exact-match summaries, JSONL logging, and deterministic CPU mock.
Oracle crop geometry is necessarily ours; oracle images are resized like official search crops.

Clone with submodules before installing:

```bash
git clone --recurse-submodules <repo>
cd ideas/ug-search-multiregion
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

For real runs, follow `third_party/ug-framework/README.md` to create its `ug` environment, including
Flash Attention, then install this package with `pip install -e '.[gpu]'`.

## Official baseline first

The paper reports **86.9 on V* Bench** for UG-Search with Qwen2.5-VL-7B (Table 1 of
[arXiv:2510.00705](https://arxiv.org/abs/2510.00705)). Before trusting Step 0, reproduce it with the
setup in the official `scripts/ug_qwenvl.sh`: Qwen2.5-VL-7B-Instruct, Flash Attention 2, one crop,
visual crop ratio 2, batch size 1, and the complete V* Bench evaluation split. Use `--limit` only
for a smoke run; a limited run cannot be compared to 86.9.

```bash
ug-baseline --output outputs/ug-baseline
# inspect the exact official lmms-eval invocation without loading a model
ug-baseline --dry-run
```

## Multi-region experiments

Step 0 retains official top-1 and compares joint top-k and available oracle crops. Step 1 additionally
starts at the lowest-entropy official window and greedily adds a window only while joint entropy
falls. Real-run defaults match the official Qwen V* setup: `Qwen/Qwen2.5-VL-7B-Instruct`, visual
crop ratio 2, and official 50%-stride square windows.

```bash
ug-step0 --benchmark vstar --dataset /data/vstar.json --k 3 --output outputs/vstar-step0
ug-step1 --benchmark vstar --dataset /data/vstar.json --k 3 \
  --min-gain 0 --max-greedy-crops 6 --output outputs/vstar-step1
```

`--visual-crop-ratios` accepts comma-separated official ratios for exploratory sweeps. Dataset rows
may come from JSON, JSONL, CSV, or TSV and need an image path, question, answer, and category.
Optional `boxes`/`oracle_boxes`/`gt_boxes` are per-object `xyxy` coordinates in pixels or `[0,1]`.
V* spatial/relative-position and HR-Bench FCP/cross-object rows are selected.

`results.md` and `results.json` contain accuracy summaries. `predictions.jsonl` records answers,
official proposal boxes, selected crop IDs, and entropy. CPU smoke runs preserve this full path while
substituting only deterministic model scores:

```bash
ug-step0 --dry-run --output outputs/smoke-step0
ug-step1 --dry-run --output outputs/smoke-step1
```
