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
