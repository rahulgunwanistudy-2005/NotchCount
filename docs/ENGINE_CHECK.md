# Engine check: real photos, real models, known truth

Run on 2026-10-21 with `scripts/engine_check.py` against a local API (schema `notchcount_test`) and the production worker code. Rerun any time: start the API with `NC_DB_SCHEMA=notchcount_test`, then `uv run python scripts/engine_check.py`.

## What was real and what was synthetic

- **Real:** 16 street-dog photos from Wikimedia Commons (CC BY-SA 4.0, see `packages/pipeline/tests/CREDITS.md`) and one street photo with people and a bus. They went through the production path end to end: HTTP upload with hash and pass checks, YOLO11s detection, blurring with the re-detection check, crops, DINOv2 int8 embeddings, candidate pairs along the route, labels through the API, logistic training, and the sampled Chapman estimate (B = 2000, seed 20261021).
- **Synthetic:** pass 2. There is no second walk yet, so pass 2 is the same dogs' photos re-shot by transforms: mirrored, recropped to 86 to 95%, rotated up to 4°, and relit. Walk 1 had dogs 1 to 13 and walk 2 dogs 4 to 16, so the true overlap is known. The labels were the known truth, not a person's judgement.

## Results

| Check | Result |
|---|---|
| Photos uploaded and processed | 27 of 27, 0 failed, 0 originals left in quarantine |
| Privacy | Street photo: 4 people and 1 bus blurred, re-detection found no visible person |
| Dog detection | 24 dog crops from 26 dog photos. One dog (lying on its back) was missed in both walks, as in the P2 spike |
| Candidate pairs | 83, containing all 9 true cross-walk matches among detected dogs |
| Similarity | Mean cosine 0.88 for same dog, 0.44 for different dogs |
| Match model | Trained on 62 labels, held-out AUC 1.00 on 21 pairs (9 positives overall) |
| Counts the engine found | n1 = 12, n2 = 12, m2 = 9 |
| True counts (dogs the detector found) | n1 = 12, n2 = 12, m2 = 9 (exact) |
| Population estimate | 15.9 (95% range 15.1 to 21.6); plain Chapman 15.9 (15.1 to 21.4) |
| Truth | 15 distinct dogs detected, 16 photographed: both inside the range |
| Sterilised share | Not reported: no ear labels were given, and the engine correctly reports no share instead of a guess |

## What this does and does not show

- It shows the pipeline is real and wired correctly. Photos in give the right counts out, privacy holds, and the estimator's range covers the truth.
- **The matching result is optimistic.** Transformed copies of one photo are far easier to match than two different photos of a dog taken on different mornings. The AUC on real walk pairs will be lower; `docs/MODEL_REPORT.md` reports it from the team's labels.
- **Speed:** about 1 s of model compute per photo on the laptop. Most of an ingest is database time: about 150 ms per round trip from the laptop to Supabase in Mumbai, and each photo blob costs about 0.4 s to send. With one job loop the 27-photo backlog took 233 s (8.6 s per photo). With blob writes batched and 4 concurrent loops per worker (DECISIONS D-22), the same backlog took **68.5 s (2.5 s per photo)**, with identical counts and estimate. On the live site, the worker kept pace with 26 sequential uploads and finished 10 s after the last one.
