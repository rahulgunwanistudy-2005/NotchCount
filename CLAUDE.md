# NotchCount: rules for every session in this repo

- Source of truth: `docs/BIBLE.md` (technical), `SESSION_PROMPT.md` (schedule, priorities), `docs/DESIGN_BRIEF.md` (UI). Read `PROGRESS.md` first to see where the build stands.
- Never fabricate data, metrics, quotes or screenshots. Synthetic data only in tests and `sim/`, always labelled.
- Verify any external API, model, license or platform limit against current docs before depending on it; log it in `docs/DECISIONS.md` with the date.
- `packages/notchcount_stats` stays pure (no I/O). Estimates are seeded and store code version, params and data hash.
- Blur people and plates before storing any image. No public page shows individual unsterilised dog locations.
- No email is sent without a logged-in team member pressing Approve. No model reads or acts on inbound email.
- Run `make check` before every commit. A gate is passed only when its checks ran in this session.
- UI follows the frontend-design skill and the design brief; review screenshots at 375 px and 1280 px before calling a screen done.
- Update `PROGRESS.md` and `docs/AI_DISCLOSURE.md` at every gate.
- Ask the team only for keys, field data, labels, consent questions and decisions marked HUMAN.
