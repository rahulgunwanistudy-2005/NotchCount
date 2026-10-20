# Progress

Read this first. Newest phase at the top.

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
