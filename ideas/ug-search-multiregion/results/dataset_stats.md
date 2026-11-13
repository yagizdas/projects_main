# Dataset statistics

Generated from the Hugging Face sources used by `prepare-data` on 2026-11-13.

| benchmark | total samples | samples mentioning 2+ target objects | 2+ targets with usable GT boxes | example question IDs |
|---|---:|---:|---:|---|
| V* Bench | 191 | 54 | 54 | 115, 116, 118, 120, 121 |
| HR-Bench | 1,600 | not machine-identifiable from the published fields | 0 | — |

V* counts use `target_object` and require at least two corresponding, positive-area `bbox_target`
boxes. The 54 qualifying rows are a subset of the 76 relative-position questions (the remaining
22 rows identify only one target). The bbox-restored V* export converts the source `[x, y, w, h]`
coordinates to the loader's `[x1, y1, x2, y2]` representation.

HR-Bench has 800 questions in each of its 4K and 8K splits. Its published Hugging Face schema is
`index`, `question`, `answer`, `category`, `A`–`D`, `cycle_category`, and `image`: it provides
neither target-object annotations nor ground-truth boxes. Consequently multi-object membership
cannot be counted reliably from structured targets, no samples qualify for oracle crops, and this
project enables oracle comparisons for V* only.
