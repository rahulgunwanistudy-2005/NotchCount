# Re-identification benchmark on real dog photos

How well does NotchCount's embedder tell individual dogs apart, on **different real photos of the same dog**? The engine check could not answer this, because its second walk was a transformed copy of the first.

- **Data:** WildlifeReID-10k on Kaggle, dog subsets only. MPDD has whole-body photos (191 dogs, 1,657 images). DogFaceNet has faces (a random 300 of its dogs, 1,762 images). Both are CC BY 4.0; used for evaluation only, not redistributed.
- **Code:** `benchmarks/reid_kaggle/reid_benchmark.py`, run as a Kaggle notebook on CPU on 2026-10-22. It installs this repository's `notchcount_pipeline` from GitHub and the models from release `models-v1`, so it measures exactly what production runs. Raw output: `benchmarks/reid_kaggle/reid_results.json`.
- **Method:** for MPDD, NotchCount's detector crops the most confident dog box, as in production. It found a dog in 884 of 1,657 images; the rest are already tight crops and were embedded whole. Every same-dog pair is scored against 20 times as many random different-dog pairs.

| Dataset | Embedder | ROC-AUC (cosine, same vs different dog) | Rank-1 (nearest other photo is the same dog) | Mean cosine, same / different |
|---|---|---|---|---|
| MPDD, whole body | DINOv2-S int8 (production) | 0.988 | 97.5% | 0.72 / 0.24 |
| MPDD, whole body | DINOv2-S fp32 | 0.989 | 97.4% | 0.73 / 0.23 |
| DogFaceNet, faces | DINOv2-S int8 (production) | 0.993 | 93.8% | 0.73 / 0.22 |
| DogFaceNet, faces | DINOv2-S fp32 | 0.993 | 94.8% | 0.74 / 0.22 |

## What it means

- Appearance alone separates individual dogs well, so cosine similarity is a strong first feature for the match model.
- int8 costs at most 0.001 AUC against fp32 at a quarter of the size and memory (DECISIONS D-13), so the production default stands, now on measured grounds.

## Why the real number on our street can be lower

- These are mostly pet and curated photos. Indian street dogs are often similar-looking (tan and brown "pariah" type), photographed at dawn, partly hidden or lying down.
- Some MPDD photos of a dog may come from the same session, which makes matching easier.
- The number that counts is the held-out AUC on the team's own labelled pairs, which the training job writes to the model record and `docs/MODEL_REPORT.md`. Uncertain pairs go to people either way.
