# UG-Search multi-region experiments

**Goal:** Experiment code that tests whether UG-Search (Akata/EML lab, uncertainty-guided MLLM visual search, public code by Sanghwan Kim et al.) leaves headroom on multi-object questions, plus a training-free fix. Written now, run later on a ~24GB GPU (no GPU in this sandbox).

**Experiments:**
- Step 0 (headroom): on V* Bench (spatial) and HR-Bench (FCP), compare answer accuracy for (a) UG top-1 crop, (b) UG top-k crops, (c) oracle crops around every ground-truth object the question mentions. Output a results table.
- Step 1 (greedy set selection): pick the lowest-entropy crop, then repeatedly add the crop that most lowers the entropy of the combined crop set; stop when no gain. Compare against Step 0 settings.
- Log selected crops per sample so Step 1 picks can later serve as labels for a DETR-style proposal head (not in scope now).

**Done when:**
- One command per experiment, configurable model (default: the 8B MLLM UG-Search uses), dataset path, k, crop sizes.
- A `--dry-run` / mock-model mode runs end to end on CPU with a few fake samples, covered by tests.
- README explains setup, dataset download and how to run on a GPU.

**Notes:** Reuse/vendor UG-Search's public code where sensible rather than reimplementing. Keep everything inside `ideas/ug-search-multiregion/`. Delete this TASK.md in your final commit.
