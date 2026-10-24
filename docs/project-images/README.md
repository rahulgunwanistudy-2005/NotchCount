# NotchCount — important project images

Prepared 24 October 2026 from the project source and recorded screenshots.

## Start here

- `00-desktop-screens.png`: all 12 desktop screens at a glance.
- `00-phone-screens.png`: all 12 phone screens at a glance.
- `00-offline-capture-demo.png`: camera ready, three captures offline, and successful reconnect.
- `00-human-review-demo.png`: populated pair and ear review controls.
- `logic/01-how-notchcount-works.png`: the complete user journey.
- `logic/02-system-architecture.png`: the services behind the screens.

## App screenshots

`screens/` contains the original full-page PNGs at 1280 px and 375 px: landing, sign in, home, survey dashboard, pair labels, ear labels, review queue, public report, case file, team, field card and system health. These are the repository's saved screenshots from 23 October 2026, copied without altering their pixels. Per the project README, the demo uses real street-dog photos and a synthetic second pass made by transforming the first-pass photos. Results on those screens are demo results, not a completed two-morning field survey.

Three additional capture images were recorded locally at 375 CSS px and 2× resolution. The application UI and IndexedDB queue are real; the API responses are mocked and the camera shows Chromium's synthetic test pattern. They demonstrate 3 shots queued while offline and 3 uploads to the mock endpoint after reconnect, not production upload or server processing. The shots alternate side/head/side, so the displayed dog count is 2. See `capture-check.json`.

Four populated review screenshots (`label-pairs-demo-*` and `label-ears-demo-*`) show the actual app at phone and desktop widths with mocked task data and the real fixture crop. The pair repeats the same sample photograph; this is a control demonstration, not a cross-morning matching result. The ear is not labelled or claimed to be notched. The older saved label screenshots are also preserved, even where the queue is empty.

## Behind-the-scenes logic

1. `logic/01-how-notchcount-works.png` — setup, walks, processing, review, estimate and filing.
2. `logic/02-system-architecture.png` — SvelteKit PWA, FastAPI, Postgres/PostGIS/pgvector, worker and Agentboxd.
3. `logic/03-life-of-a-photo.png` — upload validation, quarantine, redaction, verification, crop/embedding and safe storage; includes the privacy-failure branch.
4. `logic/04-dog-matching-and-ear-review.png` — feature extraction, candidate pairs, probabilities, labels, training and uncertainty.
5. `logic/05-estimation-logic.png` — Chapman estimate and 2,000 uncertainty draws; the numerical example is the documented engine check.
6. `logic/06-offline-capture-and-upload.png` — local save, undo, retries, upload state and pass completion.
7. `logic/07-database-logic.png` — simplified core data relationships, not the complete entity schema.
8. `logic/08-from-estimate-to-case-file.png` — reports, drafts, admin-approved sending and verified replies.

## Actual model output and validation

- `evidence/09-real-dog-pipeline.png`: the installed detector/embedder applied to the repository dog fixture, showing the real crop and features.
- `evidence/10-real-privacy-pipeline.png`: actual redacted output plus the result of checking for unredacted person regions.
- `evidence/processed-dog.jpg`, `dog-crop.jpg`, `privacy-redacted.jpg`: unannotated pipeline outputs from that run.
- `pipeline-check.json`: machine-readable counts, confidence, quality, embedding size, metadata check and model version.
- `evidence/estimator-validation.png`: existing chart from synthetic-survey validation, copied from `docs/estimator_validation.png`. Read `docs/ESTIMATOR_VALIDATION.md` for the experiment and limitations. It does not measure field accuracy.

Technical diagrams describe implemented source code, not screenshots of server consoles or evidence that every external integration is currently available. Hidden ears remain unknown; an ear model requires labels/training; the example engine check correctly reports no sterilised share without ear labels. Population estimates describe the surveyed route and carry the assumptions and limitations documented by the project.

## Photo attribution

- Dog fixture: “Street Dog 03” by Slyronit, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Street_Dog_03.jpg), CC BY-SA 4.0. Pipeline-derived dog outputs retain attribution and the same licence.
- Street fixture: `bus.jpg`, [Ultralytics assets](https://github.com/ultralytics/assets), AGPL-3.0; privacy-redacted derivatives retain that licence.
- Existing app screenshots retain the project's original assets and credits; see root `README.md` and `packages/pipeline/tests/CREDITS.md`.

## Sources and regeneration

Diagrams were checked against `README.md`, `docs/ARCHITECTURE.md`, `docs/ENGINE_CHECK.md`, `apps/web/src/lib/queue.ts`, the capture page, API upload/report/case routes, `db/models.py`, worker ingest/analysis, and the pipeline/statistics packages.

Run the local web preview on 127.0.0.1:4176, then `node scripts/capture_project_images.mjs` using the project's Playwright installation. Run `.venv/bin/python scripts/export_project_images.py` to regenerate diagrams, evidence and the archive. No production credentials or database are needed.
