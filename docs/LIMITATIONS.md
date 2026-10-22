# Limitations

Written as we find them. Nothing here is hidden from the report or the video.

## Method

- **Closed population over 24 to 48 hours.** Dogs that arrive or leave between passes break the assumption and bias the estimate.
- **Heterogeneous catchability biases Chapman low.** Some dogs are always in view and some hide. The simulation report quantifies this; we do not correct for it.
- **The estimate covers the route corridor, not the ward.** Scaling up needs a sampling plan over many routes.
- **Sterilised share counts only dogs whose ear was visible.** If hidden-ear dogs differ from the rest (for example puppies), the share is biased. The report says how many dogs were excluded.
- **Intervals can still be slightly too narrow when matching is uncertain** (synthetic validation, `docs/ESTIMATOR_VALIDATION.md`). With 5% of true matches scored like look-alikes, 95% ranges contain the truth 90.8% of the time against a 93% target. That is up from 86.6% with the BIBLE's pairwise sampler (DECISIONS D-21). With 5% false merges they reach 92.3%, within Monte Carlo error of the target. The review queue sends uncertain cross-walk pairs to people first, which removes this error at its source.
- **Real re-identification is harder than our engine check.** The engine check matched transformed copies of the same photo. The real-photo benchmark (`docs/REID_BENCHMARK.md`) measures DINOv2 on different photos of the same dogs, and the team's own labelled pairs give the final number (`docs/MODEL_REPORT.md`).
- **An ear-notch marks a dog that went through ABC at some point.** It says nothing about current rabies vaccination, since vaccination wanes. The 70% line is a benchmark from rabies-control literature, not a guarantee.

## Software, as of P1

- Sign-in uses one-time invite links until MojoAuth is integrated (DECISIONS D-02).
- Images are stored in Postgres until a Supabase Storage key is set (D-05). The free database is 500 MB.
- The interim host (Render free tier) sleeps when idle, so the first request after a quiet period can take about a minute. The capture screen opens from the phone's offline cache, and uploads retry.
- Uploads run while the app is open. If a walker closes it with photos queued, they upload the next time the app opens. Nothing is lost.
- Hindi is not yet available (strings await review by a Hindi speaker).
