# Decisions and verifications

Every external dependency checked against its own docs, with the date. Every deviation from the build pack, with the reason. Newest entries at the bottom of each section.

## Verifications

| Date (IST) | Thing | What was checked | Result |
|---|---|---|---|
| 2026-10-20 | Neighborhood Hacks sponsors | neighborhoodhacks.org and the Devpost page | Deployxa (deployxa.com), Agentboxd (agentboxd.com) and MojoAuth are listed sponsors. |
| 2026-10-20 | Supabase | Created project `notchcount` (ap-south-1, free tier, $0/month quoted by the API). Extensions queried live | `postgis` 3.3 and `vector` 0.8.2 installed in schema `extensions`. Session pooler `aws-0-ap-south-1.pooler.supabase.com:5432` accepts a custom login role (`notchcount_app.<ref>`); `aws-1` does not know the tenant. |
| 2026-10-20 | MojoAuth | mojoauth.com/llm-guide, /docs/llm-reference-guide, SDK pages | Documented: email OTP (`POST https://api.mojoauth.com/users/emailotp`, `x-api-key`), phone (SMS) OTP via SDK methods, `POST /token/validate`, JWKS at `/.well-known/jwks.json`. WhatsApp OTP appears only in a third-party catalogue, so it is unverified. Not integrated yet: no API key. |
| 2026-10-20 | Agentboxd | github.com/agentboxd/agentboxd README, agentboxd.com/docs index | MIT. Base URL `https://api.agentboxd.com/v1`, keys start `mr_`, `inboxes.create` is idempotent on `client_id`, signed webhooks with SDK verifiers, messages carry SPF/DKIM/DMARC results and an injection label, `extracted_text` strips quoted history. Doc pages exist for `/docs/drafts` and `/docs/webhooks`, but endpoint paths, header names and key scopes are not in the fetched text. Recheck with an API key before P5. |
| 2026-10-20 | Deployxa | deployxa.com | Git or Docker deploys, CLI, REST API, MCP server. Free tier: 3 projects, 512 MB RAM, 1 concurrent build. Background jobs and managed databases only on paid plans. No public docs URL found; needs the team's account. |
| 2026-10-20 | Fonts | Google Fonts CSS API; npm `@fontsource-variable/anek-devanagari` 5.3.0 and `@fontsource/mukta` 5.3.0 (both OFL-1.1) | Anek Devanagari has Devanagari, Latin and Latin-ext subsets, weight 100 to 800 and width 75% to 125%. Mukta has Devanagari and Latin. Self-hosted from npm so the field app makes no third-party font request and works offline. |
| 2026-10-20 | Map tiles | openfreemap.org | Free, no key, no request limits on the public instance, commercial use allowed, attribution required (MapLibre shows it). Style `https://tiles.openfreemap.org/styles/positron`. |
| 2026-10-20 | MapLibre GL | npm `maplibre-gl` 6.15.0, BSD-3-Clause | v6 needs `setWorkerUrl()`; the worker is bundled through Vite's `?url` import. |
| 2026-10-21 | Agentboxd API | agentboxd.com/docs/api, /docs/drafts, /docs/webhooks | `Authorization: Bearer`. `POST /v1/inboxes` (idempotent on `client_id`), `POST /v1/inboxes/:id/drafts`, `POST /v1/inboxes/:id/drafts/:draftId/send` (with `Idempotency-Key` and `expected_content_sha256`, so the approved content is exactly what was reviewed; 409 `draft_changed` otherwise). Attachments are `{filename, content_type, content_base64}`. Key permissions: draft-only key = `drafts:read` + `drafts:write`; send key adds `messages:send`. Webhooks: `X-Mailroom-Timestamp` + `X-Mailroom-Signature` = hex HMAC-SHA256(secret, "<ts>.<raw body>"), reject skew over 300 s. Event `message.received` carries `thread_id`, `message.extracted_text`, `labels`. Exact names of the injection and DMARC labels are not on these pages; treat any label we do not recognise as held. |
| 2026-10-20 | Render (interim host) | Connected Render account; free web service in Singapore | 512 MB, sleeps when idle. Used tonight because Deployxa needs the team's account (see D-04). |

## Decisions

**D-01 Licence: AGPL-3.0.** Lets us use Ultralytics YOLO if it measures best in P2 and matches an open civic tool. If the detector chosen in P2 is permissive, the licence stays AGPL anyway.

**D-02 Interim sign-in: one-time invite links.** No MojoAuth key yet, and pass 1 is tomorrow at dawn. A team admin creates each walker and sends a link (`/join#code`). The code sits in the URL fragment so it never reaches server logs. It is single-use, expires in 7 days, and only its SHA-256 is stored. It sits behind the same session layer that MojoAuth will use, so it is still a verified identity per observer: only the person holding the link can sign in as that walker. MojoAuth replaces it in P5 behind `AuthProvider`.

**D-03 Database schema `notchcount`, not `public`.** Supabase exposes `public` through PostgREST to the `anon` and `authenticated` roles. Our tables live in a schema those roles cannot use, owned by a dedicated login role. RLS is enabled on every table as defence in depth. Team scoping is enforced in every query and tested (`test_other_team_cannot_see_or_upload`). Tests run in schema `notchcount_test` and refuse to start otherwise.

**D-04 Hosting tonight on Render, Deployxa when the account arrives.** The capture app had to be live before pass 1. The image is one Dockerfile: web build plus API, port 8080, which matches the Docker flow Deployxa advertises. Moving costs one environment copy. The Deployxa free tier has 512 MB, and background jobs are paid. The plan is therefore the web and API service plus a worker run as a second web-type service with a health endpoint (3 projects allowed). Failing that, the worker runs on a laptop: it only needs database access.

**D-05 Images in Postgres until a storage key exists.** The Supabase MCP gives no service-role key, and Storage needs one. `BlobStore` has a Postgres implementation (`blobs` table, private) with our own HMAC-signed URLs that expire in 5 minutes. Expected size: about 400 photos at roughly 300 KB is about 120 MB, inside the 500 MB free database. Swap to Supabase Storage behind the same interface once the team pastes the service key.

**D-06 Photos upload 8 seconds after capture.** That gives an Undo window without a server-side delete endpoint. Undo works offline too.

**D-07 Pass start time comes from the phone.** Walkers may press Start pass with no signal. The server accepts a phone time up to 12 hours old and refuses future times. Photos are accepted from 2 minutes before the start to 5 minutes after the end, since the end is also stamped by the phone. Anything outside that range is rejected with a message. GPS problems are flagged (`no_gps`, `poor_gps` over 30 m, `outside_corridor`), never dropped.

**D-08 Map assets are excluded from the offline precache.** About 800 KB that only admins use, at a desk. Walkers' phones cache just the capture shell and fonts.

**D-09 Hindi is hidden until checked.** Draft Hindi strings exist in `apps/web/src/lib/i18n/hi.ts`, but the switch stays off until a Hindi-speaking team member reviews them and sets `REVIEWED = true` (DESIGN_BRIEF rule).

**D-10 Partition repair (BIBLE 3.4) made concrete.** Sampled "different" pairs and reviewer "different" decisions become cannot-link constraints. "Same" links are accepted greedily in descending probability: within-pass links first, then cross-pass links. A cross-pass merge is allowed only if the two groups share no pass, which is what one-to-one across passes means. An individual's notch status is "notched" if any of its sightings is notched (a cut ear cannot come from pose), otherwise "not notched" if any visible ear is unnotched, otherwise excluded as not visible.

**D-11 The two-pass interval comes from the sampler.** The headline range is the 2.5th to 97.5th percentile of N* over B = 2000 seeded replicates. The plain Chapman and Chao interval for the point configuration is stored next to it. If more than half the replicates have no recaptures, no population range is reported.

**D-12 Detector: YOLO11s, not YOLO11n.** Ran both on 16 CC BY-SA street-dog photos from Wikimedia Commons. 11n found a dog in 14 of 16 (it called a pale dog a "bear" at 0.88); 11s found 15 of 16. The miss is a dog lying upside down. Cost: 38 MB instead of 11 MB, slower per photo (numbers below). Ultralytics is AGPL-3.0, which matches D-01. Cow, cat, bear and sheep boxes are not relabelled as dogs: street cows are common and must never be counted.

**D-13 Embedder: DINOv2 ViT-S/14, int8 by default.** Exported from `facebook/dinov2-small` (Apache-2.0), CLS token, 224 px, the whole crop padded to a square so ears and tail stay in. Dynamic int8 quantisation: 88 MB to 24 MB. On 15 crops, the int8 vectors keep mean cosine 0.976 to the fp32 ones (minimum 0.964), and pairwise similarities correlate at 0.984. Both files are in release `models-v1`; P4 compares them on labelled pairs by ROC-AUC, and fp32 is one env var away (`NC_EMBEDDER=dinov2_vits14`).

**D-14 Ingest numbers (spike, Mac CPU, 2 threads, 17 photos, ONNX Runtime arena off):** YOLO11s plus int8 DINOv2 gives p50 736 ms, p95 1100 ms, peak RSS 313 MB. The fp32 embedder measured 327 MB peak; its latency run overlapped another job, so it is not reported. With the arena on, peak RSS was 434 MB. These fit a 512 MB worker. A shared 0.1 CPU host (Render free) would be about 10x slower, so tonight the worker runs on the team laptop against the same database (D-04). Real pass-1 numbers replace these at G2.

**D-15 Blur: pixelate, then Gaussian, on the box expanded by 12%, for every person and every vehicle.** No plate detector is bundled, so the whole vehicle is blurred (the pack's fallback). After blurring, the detector runs again on the output. If any person box is less than 60% covered by blur, the photo is marked failed and nothing from it is stored. The original stays in quarantine and is never served. EXIF is dropped by re-encoding.

**D-16 Models are distributed as a GitHub release, not in git.** `models/checksums.json` holds the SHA-256 of each file, `models/download.py` (stdlib only) fetches and verifies them, and the Docker build runs it.

**D-17 Simulation result reported as is.** S3 and S4 miss the 0.93 coverage target (0.867 and 0.895), and so does S5 (0.876). The harness was not tuned. The reason is explained in `docs/ESTIMATOR_VALIDATION.md` and in LIMITATIONS. The estimator follows BIBLE 3.4 as written; an assignment-level model is the known next step.

**D-18 Candidate pairs in Python, not pgvector kNN.** A survey has a few hundred crops, so all-pairs similarity is milliseconds and gives deterministic candidate sets. Gates: within a pass, 15 minutes or 120 m along the route (pairs under a minute apart, such as side and head shots, are always kept); across passes, 300 m along the route; then the top 8 by cosine with a 0.35 floor. Embeddings are still stored in pgvector with an HNSW index for later cross-survey search.

**D-19 Until the team has labelled pairs, scores come from a hand-set prior** and are marked `prior-uncalibrated` wherever they appear. Labels give the logistic model (D-18 features plus same-pass and colour distance). It is refit by "Train on labels" and needs at least 30 definite labels with both answers present.

**D-20 Disagreement between labellers leaves a pair undecided.** The model probability then stands. Agreement decides the pair. "Not sure" never decides. Every individual answer is kept (`pair_labels`, `notch_labels`) for the agreement rate in MODEL_REPORT.

**D-21 Match uncertainty is sampled at assignment level, not pair by pair (deviation from BIBLE 3.4, justified by validation).** BIBLE 3.4's recipe draws every candidate pair independently and then repairs to one-to-one. In simulation that loses probability: a weak true match's mass moves onto look-alikes and the repair discards it, so ranges are too narrow (S3 coverage 0.866). Now each walk-2 dog chooses one walk-1 candidate or none. The weights are likelihood ratios recovered from the calibrated probabilities, LR = odds(p) / odds(π) with π the mean candidate probability, and the walk-1 capture rate q = n1/N comes from a fixed-point iteration. Same data, 1000 replicates: S3 0.866 → 0.908, S4 0.901 → 0.923, and bias about halved. S4 is within Monte Carlo error of 0.93; S3 is still about 0.02 short. A Gibbs-style variant (refreshing q from each draw's N*) was tried and measured no better, so it was not kept. The pairwise sampler remains available (`matching="pairwise"`) and is reported side by side.

**D-22 The worker runs several job loops per process** (`NC_WORKER_CONCURRENCY`, default 4). Ingest is dominated by database round trips (about 150 ms each from the team laptop to Supabase Mumbai, see ENGINE_CHECK), so overlapping jobs raises throughput without more memory: models load once and are shared, and ONNX Runtime sessions are safe to call from several threads.

**D-23 Re-identification is benchmarked on real identity-labelled dog photos** (WildlifeReID-10k on Kaggle, dog subsets MPDD and DogFaceNet, both CC BY 4.0). The bundle's terms forbid commercial use and re-uploading; we only evaluate, attribute, and do not redistribute. The benchmark runs as a Kaggle notebook (`benchmarks/reid_kaggle/`) that installs this repo's pipeline from GitHub and the models from release `models-v1`.

**D-24 Reports can be published without filing.** "Publish report" gives a survey its public address. Previously only drafting a case email did, which tied the public report to Agentboxd keys.
