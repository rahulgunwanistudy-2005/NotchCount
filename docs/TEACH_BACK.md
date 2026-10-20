# Teach-back: one page per module

Every team member should be able to explain each part in their own words. Read a section, close the page, and explain it to someone else. If you get stuck, that is the part to ask about.

## 1. The estimate (`packages/notchcount_stats`)

We cannot see every dog, so we use mark-resight. On walk 1 we "mark" dogs by photographing them; their own coat is the mark. On walk 2 we photograph again. Say 40 dogs were seen on walk 1, 38 on walk 2, and 25 of those were already seen. Then walk 2 saw about 25/40 of the walk-1 dogs, so walk 2 sees about 62% of all dogs, and 38/0.62 is about 61. Chapman's formula is this idea with a +1 correction that stops small counts from blowing up: (41 × 39) / 26 − 1 = 60.5.

The range: we also compute how wrong 60.5 could be (its variance). The interval is built on the dogs we did not see, so it can never fall below the 53 we actually saw.

Matching is uncertain. If the software is 70% sure two photos are the same dog, we should not pretend it is 100% or 0%. So the estimator imagines 2000 versions of the matching, each pair drawn as same or different by its probability, and recomputes the total each time. The spread of those 2000 totals is the range we report. The same goes for ears the model is unsure about.

Sterilised share: notched dogs divided by dogs whose ear we could see. Dogs with hidden ears are left out and counted separately. The range uses the Wilson or Jeffreys method, which behaves well for small counts and shares near 0 or 1.

Questions to be ready for: why can the estimate be too low? (Dogs that hide are missed on both walks.) What happens with zero dogs seen twice? (No estimate. Walk again.)

## 2. Does the estimate work? (`sim/`)

We made fake streets where we know the true number of dogs, ran the same code on them 1000 times, and counted how often our 95% range contained the truth. With perfect matching it did 93% of the time. With 5% of matches missed, 87% with our method versus 81% without. That is better but short of the goal, and we explain why in the validation report rather than hiding it.

## 3. From photo to crop (`packages/pipeline`: detect, privacy, crops, features)

A detection model (YOLO) draws boxes around dogs, people and vehicles. People and vehicles are blurred before anything is saved. Then we run the detector again on the blurred photo to prove no person is still visible. Each dog box is cut out a little larger than the dog and scored for how big and sharp it is. Another model (DINOv2) turns each dog crop into a list of 384 numbers that describe how it looks. Similar dogs get similar lists.

## 4. Same dog or not? (`match.py`, `assign.py`)

For each pair of crops that could be the same dog (close in time or along the route), we compute features: how similar the 384-number lists are, how far apart along the route, how many minutes apart, and how similar the colours are. A logistic regression, trained on our own labels, turns these into a probability. We check it on labels it never saw (ROC-AUC, and whether "70% sure" is right about 70% of the time). Pairs between 20% and 80% go to a person.

## 5. The ear (`notch.py`)

The same 384 numbers from the head photo feed a three-way classifier: notched, not notched, or ear not visible. It pre-sorts; people decide whenever it is less than 80% sure.

## 6. The app (`apps/web`) and the server (`services/api`, `services/worker`)

The phone saves every photo on the phone first (IndexedDB), then uploads when there is signal. Uploading twice is harmless because the server recognises the photo's fingerprint. The server checks that the photo belongs to your pass and was taken during it. The worker is a separate program that takes jobs from a queue in the database and does the heavy work.

## 7. Filing (`routers/cases.py`)

The app writes the email to the official and shows it to us. Nothing is sent until a team admin presses Approve and send. Replies come back into the case file as plain text; no AI reads them or acts on them.

## 8. Privacy

Blur before storing. No public page shows where any single dog was seen. Images are only reachable through links that expire in 5 minutes.
