# Progress

Read this first. Newest phase at the top.

## Status (Oct 22, 17:30 IST)

- **New visual design** after the team's reference (D-25). It covers every screen: landing, public report, sign-in, the dashboard shell, survey dashboard, labelling, case file, team, field card, and a new admin health page. Data colours were checked for colour-blind separation. Every screen was shot at 375 and 1280 px; axe found no serious violations and no screen scrolls sideways.
- **Hosted worker:** the Render service now processes photos itself (D-26), so the live demo no longer needs the laptop. It is slower than the laptop, which stays the fast path on survey mornings.
- **CI:** interface tests on the built site with the API mocked, covering review keys, the public report, signed-out access and the landing page, plus `pnpm audit`.
- **Dependency audit:** pip-audit found nothing in the 54 runtime Python packages. pnpm audit found one low advisory in a build-time dependency (cookie), fixed by an override.
- **Not possible without the team:** field walks, labels, keys (Agentboxd, MojoAuth, Deployxa), the Hindi review, and the video. Mobbin needs a paid plan (D-27).

## Status (Oct 22, 13:30 IST)

- **Estimator:** assignment-level match sampler (DECISIONS D-21). Simulation coverage S3 0.866 → 0.908 and S4 0.901 → 0.923 against the BIBLE pairwise sampler, with bias about halved. S4 is within Monte Carlo error of 0.93; S3 is still about 0.02 short (documented).
- **Re-ID on real photos:** Kaggle benchmark (`docs/REID_BENCHMARK.md`). DINOv2 int8 AUC 0.988 whole-body (MPDD) and 0.993 faces (DogFaceNet); int8 is within 0.001 of fp32.
- **Throughput:** batched blob writes plus 4 concurrent worker loops. A 27-photo backlog takes 68.5 s instead of 233 s, and the live worker keeps pace with uploads.
- **Live demo:** team "Demo team (sample photos, synthetic walk 2)" on https://notchcount.onrender.com, processed by the real pipeline. Published report: `/r/bJriBIPv6Xv0`.
- **Screens:** `docs/screens/` has 21 screenshots from the live demo at 375 and 1280 px. All pass the automatic audit: no sideways scroll and no serious or critical axe violations (`audit-*.json`).
- **Field data:** none yet. The real team is untouched and the admin link (valid to Oct 27) is unused.
- **Worker:** runs on the team laptop (`NC_WORKER_CONCURRENCY=4 uv run nc-worker`). It now backs off during network outages instead of flooding the log.

## Status check (Oct 21, 19:30 IST)

- **Field pass 1 has not happened in the app.** Production has the team and admin only: no route, survey or photos, and the admin sign-in link (valid to Oct 27) is unused. HUMAN: draw the route, create the survey, invite walkers, then walk.
- **History cleaned and pushed:** all commits on GitHub are free of AI attribution (force-pushed with the team's approval). Render redeployed the latest code, verified live.
- **Engine verified on real photos:** `docs/ENGINE_CHECK.md` (real photos, real models; pass 2 synthetic). Counts exactly match truth; the range covers the true N.
- **Live:** offline-capture Playwright passes against https://notchcount.onrender.com, and the production worker ingested the uploads.
- **CI:** fixed. The unit job lacked env config, and gitleaks failed on the root commit; it now scans full history with the CLI. A local check found no secrets in history.
- **Speed:** about 150 ms per DB round trip from the laptop to Supabase Mumbai dominates ingest (3.5 s wall, 1 s compute). Blob writes are now batched. The worker should be hosted in the database's region.

## P4 Re-ID, calibration, notch, review queue: code done, waiting for labels (Oct 21, 01:15 IST)

- Candidate pairs, match features, logistic match model with held-out AUC and reliability, within-pass clustering plus Hungarian assignment, 3-way ear classifier, review queue, and labelling screens (pairs and ears, keyboard S/D/N and N/O/V).
- Worker jobs: `match_survey`, `train_models`, `notch_survey`, `estimate` (two-pass sampled Chapman, or single-pass when only one pass exists or the passes are not comparable).
- **Waiting on HUMAN:** label pass-1 pairs and ears this evening (FIELD_PROTOCOL labelling session). G4 metrics come from those labels.

## P3 Estimator and simulation: G3 run, two targets missed (Oct 21, 00:50 IST)

- Worked example and property tests pass. `docs/ESTIMATOR_VALIDATION.md` and its plot come from 1000 replicates per scenario.
- Coverage: S1 0.931, S2 0.634 (heterogeneity, expected), S3 0.867, S4 0.895, S5 0.876, S6 0.810. S3 and S4 miss 0.93. The cause is explained in the report and in LIMITATIONS; the harness was not tuned.

## P2 Ingest pipeline: code done, G2 waits for pass-1 photos (Oct 21, 00:30 IST)

- YOLO11s detection, blur of people and vehicles with a re-detection check, crops with quality scores, DINOv2 int8 embeddings. The worker job is tested end to end against the test database.
- Spike on 17 sample photos: p50 736 ms, p95 1.1 s, peak 313 MB (DECISIONS D-14).
- A worker runs on the team laptop against production (`uv run nc-worker`), so pass-1 photos are processed as they arrive.

## P1 Field capture PWA: G1 passed (Oct 20, 22:40 IST)

- **Live:** https://notchcount.onrender.com (interim host, DECISIONS D-04). Health: `/healthz`.
- **Evidence:** Playwright `apps/web/e2e/offline-capture.spec.ts` passes locally and against the live URL: three photos taken offline (fake camera), reconnect, all three arrive with shot type, GPS and accuracy, no flags.
- **Done:** sign-in by one-time link, team admin (people, route drawing, surveys), capture screen (camera, side then head steps, GPS accuracy, offline queue with Undo, wake lock), field card, offline shell.
- **Not yet verified on a real phone:** install to home screen, 10 photos in airplane mode, reconnect. HUMAN, tonight.
- **Next:** P2 ingest (detect, blur, crop, embed) on pass-1 photos.
- **Risks:** Render free tier sleeps (first upload after a quiet hour waits about a minute; the queue retries). No MojoAuth or Agentboxd keys yet.

## P0 Setup: G0 passed except the Deployxa hello-world (Oct 20)

- Monorepo, `make check`, CI workflow, Supabase project with PostGIS and pgvector, schema migrated.
- Estimator core with the BIBLE worked example and property tests (23 tests).
- API tests against Postgres (9 tests: auth on every route, team isolation, idempotent upload, pass rules).
- Spikes: see `docs/DECISIONS.md` verifications. Deployxa and MojoAuth need the team's accounts; the Agentboxd endpoint details need a key.
