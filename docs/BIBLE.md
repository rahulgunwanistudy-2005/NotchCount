# NotchCount project bible

Spec for the build. Section numbers are referenced from `SESSION_PROMPT.md`. Where this file names an external API, model, license or limit, it is a starting point to verify, not a fact to rely on.

## 1. Problem and evidence

India's legal approach to street dogs is Animal Birth Control: catch, sterilise, vaccinate, ear-notch, return to the same place. Whether it works depends on coverage, and nobody outside the operator measures coverage.

- 37,17,336 dog-bite cases and 54 suspected rabies deaths reported in 2024 (Lok Sabha reply): https://ianslive.in/centre-steps-up-stray-dog-control-measures-over-37-lakh-dog-bite-cases-in-2024--20250722185614
- 30,43,339 bites in 2023: https://eparlib.nic.in/bitstream/123456789/2978385/1/AU1290_jJGiDc.pdf
- Chandigarh: corporation claimed about 20,000 dogs sterilised since 2015 against a 2018 census of 12,920 strays; residents call the drive paper-only: https://www.tribuneindia.com/news/chandigarh/dogged-by-strays-chandigarh-residents-say-sterilisation-drive-only-on-paper-375979
- Supreme Court, Aug 22, 2025: dogs released only after sterilisation and immunisation; case widened to all India: https://moneylife.in/article/supreme-court-allows-stray-dogs-release-from-shelters-after-vaccination-but-says-no-to-public-feeding/78054.html
- Dhaka mark-resight: mean coverage 60.6%, only 8 wards above the 70% threshold used for rabies control: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4433337/
- Ear-notch as the mark in mark-resight surveys of roaming dogs, Rajasthan: https://bmcvetres.biomedcentral.com/track/pdf/10.1186/1746-6148-7-46
- Photographic sight-resight used for population estimates (Kerman, Iran): https://dogwelfareproject.org/research/population-estimate-model-sterilization-impact-iran-kerman/

Closest existing tools and the gap: ICAM Talea (manual tallies by trained surveyors, no individual ID); operator-side geotag apps (the operator audits itself); research sight-resight (manual photo matching by scientists). NotchCount is citizen-run, automates matching with human review, and carries uncertainty into the result.

## 2. Users and core flows

| User | Job | Device |
|---|---|---|
| Walker (student or resident) | Photograph every dog on a fixed route, twice | Cheap Android phone, outdoors, morning light, patchy data |
| Reviewer (team member) | Confirm uncertain matches and notch calls | Phone or laptop |
| Team admin | Draw routes, run estimates, file the case | Laptop |
| Authority recipient (ABC officer, ward office) | Read a credible one-page report, reply | Email, browser |
| Public / RWA | See route-level coverage, no individual dog locations | Browser |

Flow: draw route → pass 1 walk → ingest → label pairs and notch (first time only) → pass 2 walk (same time next day) → match and review → estimate → report → approve draft → send → replies tracked.

## 3. Statistics

### 3.1 Model and assumptions

Two-sample (or k-sample) mark-resight on one route. A "capture" is photographing an individual dog during a pass. The "mark" is the dog's own appearance, recovered by re-identification. Assumptions, shown in the UI's assumptions panel in plain words:

1. Closed population over the passes (passes within 24 to 48 hours, same route, same start time).
2. Each dog has some chance of being photographed on each pass; heterogeneity exists and biases estimates low; the simulation report quantifies this.
3. Re-identification errors are modelled, not ignored: false merges and false splits are represented by match probabilities and human review.
4. The estimate is for dogs using the route corridor, not the whole ward.

Notation: n1, n2 individuals seen in passes 1 and 2; m2 individuals seen in both; Mt1 = n1 + n2 − m2 distinct individuals seen.

### 3.2 Chapman estimator and interval

N̂ = (n1 + 1)(n2 + 1) / (m2 + 1) − 1

Var(N̂) = (n1 + 1)(n2 + 1)(n1 − m2)(n2 − m2) / ((m2 + 1)²(m2 + 2))

Analytic 95% interval (Chao log-normal), which never goes below Mt1:

f0 = N̂ − Mt1, C = exp(1.96 · sqrt(ln(1 + Var / f0²))), interval = [Mt1 + f0 / C, Mt1 + f0 · C]. If f0 ≤ 0, report [Mt1, Mt1] and flag "every dog seen twice; population likely near count".

If m2 = 0: no estimate (see SESSION_PROMPT section 7).

### 3.3 Three or more passes

Schnabel with Chapman-style correction: N̂ = Σ_t (C_t · M_t) / (Σ_t R_t + 1), where C_t = individuals seen in pass t, M_t = distinct individuals seen before pass t, R_t = those in pass t already seen. Library supports it; UI support is on the cut list.

### 3.4 Carrying match uncertainty

Every candidate pair (a, b) of dog sightings gets a calibrated probability P(same) from the match model (section 5.3). Pairs a reviewer decided are fixed at 0 or 1.

For b = 1..B (default B = 2000, seeded):

1. Sample a match configuration: draw each unresolved pair as same/different from its probability, then repair to a valid partition (one-to-one across passes, transitive within a pass) by greedy acceptance in descending sampled-score order.
2. Compute (n1, n2, m2) and N̂_b, Var_b.
3. Draw N*_b from the Chao log-normal for that configuration.
4. Sample notch status for each individual with an unresolved notch call from its calibrated probability; individuals with no visible ear stay excluded.
5. Draw sterilised share s*_b from Beta(x + 0.5, k − x + 0.5) (Jeffreys) where x notched, k individuals with a visible ear.
6. Coverage deficit d*_b = max(0, 0.70 · N*_b − s*_b · N*_b).

Report: median and 2.5 / 97.5 percentiles of N*, s*, d*; also the plain Chapman number for the fully reviewed configuration. Store B, seed, model versions and the data hash with the estimate.

### 3.5 Sterilised share and the 70% line

Share of individuals with a visible ear that carry the notch. Single-pass mode reports this with a Wilson interval: centre = (p + z²/2k) / (1 + z²/k), half-width = z · sqrt(p(1 − p)/k + z²/4k²) / (1 + z²/k).

The 70% line comes from rabies-control literature on vaccination coverage (Dhaka paper above). An ear-notch marks a dog that went through ABC, which includes vaccination at that time; vaccination wanes, so the UI says "sterilised share" and treats 70% as a benchmark, not a guarantee of rabies protection.

Ear and side of notch vary by city and operator. `config/notch_conventions.yaml` sets ear (left, right, either) and shape for the city; reviewers can override.

### 3.6 Claims check (optional, cut list item 2)

If the municipality publishes sterilisation numbers for an area, the admin enters claimed count C, the area it covers, and the period. The UI shows, for an annual survival range s in [0.5, 0.9] supplied by the admin, how many notched dogs should still be alive, against the route-level estimate scaled by area. Label it rough, show the full sensitivity band, never a single verdict.

### 3.7 Worked example (unit test fixture)

n1 = 40, n2 = 38, m2 = 25 → Mt1 = 53, N̂ = 60.5, Var = 17.083, SE = 4.133, Chao 95% interval [55.7, 73.6].

29 notched of 49 individuals with a visible ear → share 59.2%, Wilson 95% [45.2%, 71.8%].

Deficit at the point estimates: 0.70 · 60.5 − 0.592 · 60.5 ≈ 6.5 dogs.

### 3.8 Simulation scenarios (acceptance in `docs/ESTIMATOR_VALIDATION.md`)

1000 replicates each. Report relative bias and 95% interval coverage of N*, and coverage of s*.

| ID | N | Capture prob per pass | Heterogeneity | False split | False merge | Expectation |
|---|---|---|---|---|---|---|
| S1 | 60 | 0.6 | none | 0 | 0 | coverage ≈ 0.95 |
| S2 | 60 | mean 0.6 | Beta(2, 1.33) per dog | 0 | 0 | negative bias; report it |
| S3 | 60 | 0.6 | none | 5%, modelled | 0 | coverage ≥ 0.93 |
| S4 | 60 | 0.6 | none | 0 | 5%, modelled | coverage ≥ 0.93 |
| S5 | 15 | 0.5 | none | 0 | 0 | wide intervals; m2 = 0 rate reported |
| S6 | 60 | 0.6 | none | 5%, NOT modelled | 0 | shows why modelling matters |

"Modelled" means the simulated matcher emits calibrated probabilities with the stated error rate and the estimator uses section 3.4. S6 feeds hard decisions to plain Chapman.

## 4. Architecture

### 4.1 Components

```
Phone PWA (capture, offline queue)        Laptop web (review, report, case file)
            \                                   /
             +--------- SvelteKit web ---------+
                            |
                     FastAPI API ----- MojoAuth (verify tokens)
                      |       \
         Postgres (Supabase:   \---- Agentboxd (inbox, drafts, send, webhooks)
         PostGIS, pgvector,
         jobs table)
                      |
                   Worker (ONNX Runtime: detector, blur, DINOv2, match, notch;
                           notchcount_stats estimates)
                      |
              Supabase Storage (quarantine, blurred, crops)
```

Hosting: web, API, worker on Deployxa; data on Supabase.

### 4.2 Data model (Alembic migrations)

- `users(id, auth_subject, display_name, phone_hash, created_at)`
- `teams(id, name, city, notch_convention)`; `team_members(team_id, user_id, role)` with role in admin, reviewer, walker
- `routes(id, team_id, name, geom LineString 4326, corridor_m int)`
- `surveys(id, route_id, start_window_local, status)`
- `passes(id, survey_id, pass_no, observer_id, started_at, ended_at, locked bool)`, unique (survey_id, pass_no)
- `photos(id, pass_id, sha256 unique, taken_at, geom Point, accuracy_m, heading, storage_key, status, error)`
- `detections(id, photo_id, bbox, conf, crop_key, quality, embedding vector(384, or the chosen model's dimension), color_hist, view enum(side, head, unknown))`
- `match_pairs(id, survey_id, a_detection, b_detection, p_same, model_version, decision enum(same, different, unsure, null), decided_by, decided_at)`
- `individuals(id, survey_id)`; `sightings(detection_id, individual_id, pass_no)`
- `notch_calls(detection_id, p_notched, p_not_visible, model_version, decision, decided_by)`
- `estimates(id, survey_id, method, params jsonb, results jsonb, data_hash, code_version, seed, created_at)`
- `claims(id, team_id, authority, area_desc, count, period, source_url)`
- `cases(id, survey_id, authority_name, authority_email, agentboxd_inbox_id, status)`; `case_events(id, case_id, kind enum(draft, approved, sent, reply, held), payload jsonb, actor_id, created_at)`
- `jobs(id, kind, payload jsonb, status, attempts, run_after, last_error, locked_by, locked_at)`
- Row-level access by team on every team-owned table.

### 4.3 API (prefix `/api/v1`)

| Method and path | Purpose |
|---|---|
| POST `/auth/session` | Exchange a MojoAuth token for our session after server-side verification |
| GET `/me` | Current user, teams |
| POST/GET `/teams`, `/routes`, `/surveys` | Setup |
| POST `/surveys/{id}/passes`, POST `/passes/{id}/end` | Pass lifecycle, integrity rules enforced |
| POST `/passes/{id}/photos` | Multipart upload, idempotent on sha256 |
| GET `/surveys/{id}/labeling/pairs`, POST `/labels` | Calibration labelling (stratified by similarity band) |
| GET `/surveys/{id}/review/next`, POST `/review/{item_id}` | Review queue |
| POST `/surveys/{id}/estimates`, GET `/estimates/{id}` | Enqueue and read estimates |
| GET `/reports/{slug}`, GET `/reports/{slug}.pdf` | Public report (route-level only) |
| POST `/cases`, POST `/cases/{id}/drafts`, POST `/cases/{id}/drafts/{draft_id}/approve`, GET `/cases/{id}/timeline` | Filing |
| POST `/webhooks/agentboxd` | Inbound replies and status |
| GET `/admin/health` | Queue depth, failures, model versions |

### 4.4 Repo layout

```
apps/web/                 SvelteKit PWA
services/api/             FastAPI app, Alembic
services/worker/          job runner
packages/notchcount_stats/  pure estimator library (no I/O)
packages/pipeline/        detect, blur, crop, embed, match, notch
models/                   export scripts, checksums, download script (no weights in git)
sim/                      simulation harness and report generator
config/                   notch_conventions.yaml, thresholds.yaml
docs/                     this pack plus generated reports
.github/workflows/        CI
```

### 4.5 Jobs

`ingest_photo` → `pair_candidates` (after pass end) → `match_survey` → `notch_survey` → `estimate`. All idempotent, retried with backoff, dead-lettered with reason.

## 5. Pipeline details

### 5.1 Detection and privacy

Detector input 640 px. Keep `dog` boxes above a confidence threshold tuned on pass-1 photos (start 0.35). Blur `person` boxes with a strong Gaussian on an expanded box before storing anything. Vehicles: blur plates if a plate detector is available, otherwise the front and rear region of vehicle boxes. Test: re-run the detector on stored images; no person box may overlap an unblurred region.

### 5.2 Crops and quality

Pad dog boxes by 10%. Quality = f(box area, Laplacian variance, truncation at image edge). Crops below the floor are kept for audit but excluded from matching and shown to reviewers only on request. View label: the protocol asks for a side shot then a head shot; the second photo in a burst within 20 s near the same spot is tagged `head`.

### 5.3 Matching

Features per pair: cosine similarity of DINOv2 embeddings (max over the two individuals' crops), distance along the route between sightings (project points to the route), time gap, HSV colour histogram chi-square distance. Logistic regression fitted on labelled pairs (target at least 150 pairs, at least 50 positives, stratified across similarity bands). Report ROC-AUC and a reliability diagram on a 25% held-out split.

Within a pass: average-linkage agglomerative clustering on 1 − P, cut at 0.5; any cluster with an internal pair below 0.2 goes to review. Across passes: Hungarian assignment on −log P with a "no match" option priced at −log(1 − 0.5). Pairs with 0.2 < P < 0.8 enter the review queue, ordered by influence on the estimate (pairs that change m2 first).

### 5.4 Notch classifier

Input: head-view crops (fall back to side crops). Features: DINOv2 embedding at 224 px; try 448 px if accuracy is poor and latency allows. Three classes: notched, not notched, ear not visible. Logistic regression with class weights, calibrated; target at least 200 labelled crops. Calls with max probability below 0.8 go to review. If held-out accuracy is weak, the README says the model pre-sorts and humans decide; that is still a valid product.

## 6. Sponsor integration

- **MojoAuth.** Interface `AuthProvider.start(identifier)`, `.verify(code or token) → subject`. Preferred channel WhatsApp OTP, then SMS OTP, then email OTP, depending on what the account plan allows (verify). Server verifies tokens; sessions are our own short-lived JWTs in httpOnly cookies. Why load-bearing: every pass must be attributable to a verified observer so the data can be trusted by an official, and phone OTP lets walkers without email join.
- **Agentboxd.** One inbox per case (`client_id = case-{id}`, idempotent). Drafts created with the draft-only key. Our Approve button calls send with the send-capable key, records `approved` and `sent` events with the approver's id. Inbound via webhook; store text as untrusted; surface Agentboxd labels (injection risk, DMARC fail) as held. Verify endpoints, attachment support, webhook signing and key scopes in P0.
- **Deployxa.** Three services from one repo (web, API, worker), env vars for secrets, health checks. Note the plan limits measured in P0.
- **Wasmer Edge (stretch).** Stateless `POST /estimate` wrapping `notchcount_stats` so other groups can run the estimator on their own counts.

## 7. Security and privacy

- Auth required on everything except public report pages and the landing page.
- Team-scoped access enforced in queries and by tests.
- Signed URLs for images, 5-minute expiry. Quarantine originals deleted after blurring.
- Rate limits: auth start 5 per 10 minutes per identifier; uploads 120 per minute per user.
- Public report shows route-level aggregates and a coarse map; individual unsterilised dog locations only in the case file for the authority and team admins.
- Webhook endpoint verifies signatures if offered, else a secret path token; payload size limits.
- No model reads or acts on inbound email content.
- Data retention note in README: what is stored, for how long, how to delete a team's data.

## 8. Test plan

| Area | Tests |
|---|---|
| Estimator | Worked example; m2 = 0; f0 ≤ 0; Schnabel at k = 2 equals n1·n2 / (m2 + 1); property tests (N̂ non-increasing in m2, N̂ ≥ Mt1, interval contains point and never goes below Mt1) |
| Simulation | Scenario table, seeded, report generated in CI on a small replicate count, full run locally |
| Pipeline | Detector on fixtures; blur verification; crop quality; idempotent re-ingest |
| Matching | Calibration on held-out pairs; Hungarian with no-match option; transitivity repair |
| API | Auth on every route; team isolation; pass integrity; upload idempotency |
| Filing | Draft never sends without approve; approve requires team admin; webhook stores replies as held when labelled |
| Web | Playwright: offline capture → reconnect → upload; review keyboard flow; report renders with intervals; axe checks |

## 9. Performance budgets (measure, then record actuals)

| Path | Budget |
|---|---|
| Shutter to saved in IndexedDB | < 300 ms on a mid-range Android |
| Ingest per photo on CPU worker | p95 < 3 s |
| Review queue next item | < 200 ms |
| Estimate run, B = 2000 | < 10 s |
| Capture route JS | < 150 KB gzipped, excluding the map |
