# NotchCount submission kit

Every bracketed value is filled by the team from the final report and the field sheet. Nothing is filled from memory or from this kit's examples.

## Devpost fields

**Name:** NotchCount

**Elevator pitch (pick one, under 200 characters):**
- Walk your street twice, photograph every dog, and find out what share are really sterilised, with the error bars an official can't argue with.
- Two morning walks and a phone camera turn "sterilisation is only on paper" into a measured number for your ward.

**Description, in this order:**

### What is the specific problem, and how do you know it's real?

Write this first; organisers call it the most important part. About 150 to 200 words. Structure: what we saw on our street, what we measured (dates, route length, dogs, notched share with range), what neighbours told us (household answers, feeder interview), why it is bigger than our street (two or three linked numbers from BIBLE section 1), why nobody measures it. Template:

> On our lane in [area, city], [personal observation, one sentence]. Our city says it sterilises street dogs, so on [dates] we walked the same [N] km route twice at dawn and photographed every dog. NotchCount found about [N̂] dogs use the route ([low] to [high]); only [p]% ([low] to [high]) carry the ear-notch that marks a sterilised dog, against the 70% benchmark used in rabies control. In [x] of [y] homes we surveyed, someone was bitten or chased this year. A feeder who has known these dogs for [years] told us [finding]. This is not just our lane: India recorded 37.17 lakh dog bites in 2024, residents in other cities call sterilisation drives "only on paper", and in August 2025 the Supreme Court ordered dogs released only after sterilisation. Yet no one outside the programme measures coverage.

### What it does
Four short paragraphs: capture offline, match and review, estimate with ranges, file with approval.

### How we built it
Stack; the pipeline; the estimator and the simulation result in one sentence ("95% intervals covered the true count in [x]% of 1,000 simulated surveys with 5% matching errors"); privacy design; sponsor tech and why each is there (MojoAuth: verified observers with phone OTP; Agentboxd: case inbox, approval before send, replies screened; Deployxa: hosting). One line on why Backboard, Spine and Momen were not used.

### Challenges
Real ones from `PROGRESS.md`, for example look-alike brown dogs, ears hidden in head photos, morning GPS drift.

### What we learned / what's next
Ward-level sampling plan, partnering with an Animal Birth Control operator, vaccination status, more cities.

### AI disclosure
From `docs/AI_DISCLOSURE.md`: tools used, what they generated, what the team designed, decided, collected, labelled, verified and wrote. Be specific; misrepresenting AI use is a disqualification ground.

**Links:** public repo, live app, video (YouTube unlisted or public).

## Video (target 3:30, hard limit 6:00, minimum 2:00)

| Time | Shot | Words (spoken by a team member) |
|---|---|---|
| 0:00 to 0:20 | Dawn on the real lane, a dog sleeping by a gate; overlay the final share | "On our lane, [p]% of the dogs are sterilised. The city's target is 70. We know because we counted." |
| 0:20 to 0:50 | Team walking, phone in hand; a neighbour (with consent, or voice only); field sheet | How we know it's real: route, dates, household numbers, feeder quote |
| 0:50 to 1:20 | Screen recording on a phone: capture in airplane mode, queue count, reconnect, uploads | "No signal on our lane at 6 am, so it works offline." |
| 1:20 to 1:50 | Review queue: two crops, Same dog; an ear call | "The app suggests matches; we decide the hard ones." |
| 1:50 to 2:30 | Report page animation from real data; range bars; "needs about [k] more" | Read the headline sentence aloud with its range |
| 2:30 to 2:55 | Case file: draft, Approve and send, the reply arriving (to a team address if the officer has not replied) | State honestly whose inbox it is |
| 2:55 to 3:20 | Simulation coverage chart, architecture diagram, blurred-faces example | One sentence each: validated estimator, clean architecture, privacy |
| 3:20 to 3:35 | Team on the lane | What's next and the ask |

Rules: every number on screen is from the real report or labelled synthetic; no mock screens; captions on; record the phone screen natively; 1080p.

## README (repo root)

1. One-paragraph what and why, with the headline result from the team's route.
2. Screenshots (capture, review, report, case file).
3. Quick start: clone, env vars, `make dev`, seed with the anonymised sample, `make check`.
4. Architecture diagram and module map.
5. The method in plain words, then the math, linking `docs/ESTIMATOR_VALIDATION.md` and `docs/MODEL_REPORT.md`.
6. Privacy and data handling.
7. Sponsor tech and why.
8. Limitations (link `docs/LIMITATIONS.md`).
9. Team, AI disclosure, license, credits (models, fonts, map tiles, Mobbin for design research).

## Rubric self-audit (fill before submitting)

| Criterion | Weight | Evidence we show | Weakest point and fix |
|---|---|---|---|
| Community Relevance | 25 | Our route, our counts, household answers, feeder interview | |
| Impact Potential | 20 | National bite data, court order, any operator can use the method | |
| Technical Execution | 20 | Live app, tests, simulation coverage, model report | |
| Creativity | 15 | Mark-resight by residents with re-ID; the audit nobody runs | |
| Presentation | 10 | 3:30 video, headline sentence with range | |
| Accessibility | 10 | Offline, phone OTP, Hindi, icons with labels, printed report | |

## Final checklist (Oct 23)

- [ ] Repo public, license present, no secrets in history (`git log -p | grep -i key` and a secret scanner).
- [ ] README quick start tested from a fresh clone.
- [ ] Live URL loads on a phone on mobile data.
- [ ] Video plays logged out, 2 to 6 minutes.
- [ ] Description includes the required "how do you know it's real" answer, filled with real numbers.
- [ ] AI disclosure present and specific.
- [ ] Every team member has read `docs/TEACH_BACK.md` and can explain the estimator and the matching in their own words.
- [ ] Submitted by 23:00 IST Oct 23; confirmation screenshot saved. Hard deadline Oct 24, 10:29 IST.
