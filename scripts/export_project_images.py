"""Export project screenshots and source-grounded engineering diagrams as PNGs."""

from __future__ import annotations

import io
import json
import math
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/project-images"
SCREENS = OUT / "screens"
DIAGRAMS = OUT / "logic"
EVIDENCE = OUT / "evidence"
for p in [OUT, SCREENS, DIAGRAMS, EVIDENCE]:
    p.mkdir(parents=True, exist_ok=True)

BG = "#F6F5ED"
INK = "#20372C"
MUTED = "#53665A"
GREEN = "#DDEAA5"
PALE = "#EAF0E1"
WHITE = "#FFFFFF"
ORANGE = "#F3D4AC"
LINE = "#80917F"
FONT = Path("/System/Library/Fonts/Supplemental")


def font(n, bold=False, serif=False):
    return ImageFont.truetype(
        str(FONT / ("Georgia.ttf" if serif else "Arial Bold.ttf" if bold else "Arial.ttf")), n
    )


def wrap(draw, text, f, width):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=f) > width and line:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


def txt(im, xy, text, size=33, color=INK, width=None, bold=False, serif=False, spacing=12):
    draw = ImageDraw.Draw(im)
    f = font(size, bold, serif)
    lines = wrap(draw, text, f, width) if width else text.split("\n")
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=f, fill=color)
        y += size + spacing
    return y


def canvas(number, title, subtitle, source, size=(2400, 1500)):
    im = Image.new("RGB", size, BG)
    d = ImageDraw.Draw(im)
    badge_width = d.textlength("NOTCHCOUNT / " + number, font=font(26, True)) + 56
    d.rounded_rectangle((80, 62, 80 + badge_width, 116), radius=27, fill=GREEN)
    txt(im, (108, 73), "NOTCHCOUNT / " + number, 26, bold=True)
    txt(im, (80, 152), title, 64, serif=True)
    txt(im, (83, 247), subtitle, 32, MUTED, width=size[0] - 170)
    d.line((80, size[1] - 115, size[0] - 80, size[1] - 115), fill="#D5DBCB", width=2)
    txt(im, (82, size[1] - 88), source, 23, MUTED, width=size[0] - 170, spacing=5)
    return im


def box(im, rect, title, body, tag=None, fill=WHITE, title_size=39, body_size=32):
    x, y, w, h = rect
    ImageDraw.Draw(im).rounded_rectangle((x, y, x + w, y + h), radius=24, fill=fill)
    ty = y + 30
    if tag:
        txt(im, (x + 30, ty), tag, 24, MUTED, bold=True)
        ty += 44
    ty = txt(im, (x + 30, ty), title, title_size, bold=True, width=w - 60, spacing=8)
    ty += 18
    end = txt(im, (x + 30, ty), body, body_size, MUTED, width=w - 60, spacing=11)
    if end > y + h - 10:
        raise ValueError(f"Overflow in {title}: {end} > {y + h}")
    return (x, y, w, h)


def arrow(im, points, label=None):
    d = ImageDraw.Draw(im)
    d.line(points, fill=LINE, width=5, joint="curve")
    x, y = points[-1]
    a, b = points[-2]
    angle = math.atan2(y - b, x - a)
    pts = [
        (x, y),
        (x - 18 * math.cos(angle - 0.45), y - 18 * math.sin(angle - 0.45)),
        (x - 18 * math.cos(angle + 0.45), y - 18 * math.sin(angle + 0.45)),
    ]
    d.polygon(pts, fill=LINE)
    if label:
        mx = (points[0][0] + x) / 2
        my = (points[0][1] + y) / 2
        txt(im, (mx + 14, my - 38), label, 25, MUTED)


def callout(im, y, title, body, fill=PALE):
    box(im, (80, y, 2240, 145), title, body, fill=fill, title_size=32, body_size=29)


def save(im, filename, folder=DIAGRAMS):
    im.save(folder / filename, optimize=True)


def grid_flow(num, title, subtitle, items, source, call=None):
    im = canvas(num, title, subtitle, source)
    positions = [(80, 350), (860, 350), (1640, 350), (1640, 810), (860, 810), (80, 810)]
    w, h = 680, 330
    for i, ((x, y), (head, body)) in enumerate(zip(positions, items, strict=False)):
        box(im, (x, y, w, h), head, body, tag=f"STEP {i + 1:02}", fill=GREEN if i == 0 else WHITE)
    arrow(im, [(765, 515), (850, 515)])
    arrow(im, [(1545, 515), (1630, 515)])
    arrow(im, [(1980, 690), (1980, 800)])
    arrow(im, [(1630, 975), (1550, 975)])
    arrow(im, [(850, 975), (770, 975)])
    if call:
        callout(im, 1200, *call)
    save(im, f"{num}-{title.lower().replace(' ', '-')}.png")


grid_flow(
    "01",
    "How NotchCount works",
    "Two morning walks become a route-level audit of street-dog sterilisation.",
    [
        (
            "Set up a route",
            "Create a team and a fixed street route. Plan comparable walks on different mornings.",
        ),
        (
            "Photograph each dog",
            "Take side and head shots. Save time and GPS with each photo, even without signal.",
        ),
        (
            "Process the photos",
            "Blur people and vehicles. Detect dogs, create crops and extract appearance features.",
        ),
        (
            "Match and review",
            "Suggest the same dogs across walks. People check uncertain matches and ear notches.",
        ),
        (
            "Estimate with ranges",
            "Use repeated sightings to estimate the total and the share with a visible sterilisation notch.",
        ),
        (
            "Share and file evidence",
            "Publish a report and PDF. Draft a case email; a team admin approves sending.",
        ),
    ],
    "Sources: README.md; docs/ARCHITECTURE.md; API, worker and web source.",
    (
        "Demo data is labelled",
        "Existing screen captures use real photos and a simulated second walk; they are not a completed two-morning field study.",
    ),
)

im = canvas(
    "02",
    "Behind the screens",
    "The web app, API and background worker share one Postgres data store.",
    "Sources: README.md; docs/ARCHITECTURE.md; services/api; services/worker; apps/web.",
)
box(
    im,
    (80, 350, 600, 290),
    "Phone + desktop",
    "SvelteKit PWA\nCamera, GPS, offline queue\nReview, reports and case file",
    fill=GREEN,
)
box(
    im,
    (900, 350, 600, 290),
    "FastAPI",
    "Sessions and team roles\nUpload and pass checks\nReview, reports and filing",
)
box(
    im,
    (1720, 350, 600, 290),
    "Postgres",
    "PostGIS: route geometry\npgvector: dog embeddings\nTables, jobs and image blobs",
)
box(
    im,
    (900, 820, 600, 340),
    "Background worker",
    "Claims Postgres jobs\nONNX detect + embed\nMatch, ear model, estimate",
    fill=PALE,
)
box(
    im,
    (80, 820, 600, 340),
    "Public report + PDF",
    "Reads stored estimates\nRoute-level totals and ranges\nNo individual dog locations",
)
box(
    im,
    (1720, 820, 600, 340),
    "Agentboxd case inbox",
    "Draft created through API\nAdmin approval permits send\nSigned webhook brings replies",
)
arrow(im, [(690, 495), (890, 495)], "HTTPS")
arrow(im, [(1510, 495), (1710, 495)], "read / write")
arrow(im, [(1200, 650), (1200, 810)], "queue + results")
arrow(im, [(1510, 990), (1620, 990), (1620, 675), (2010, 675), (2010, 650)])
arrow(im, [(380, 810), (380, 715), (870, 715), (870, 620), (890, 620)])
arrow(im, [(1720, 845), (1620, 845), (1620, 620), (1510, 620)])
callout(
    im,
    1210,
    "Keep the boundaries clear",
    "API handles rules and access. Worker runs model inference. Statistics and image-pipeline packages stay independent of HTTP.",
)
save(im, "02-system-architecture.png")

grid_flow(
    "03",
    "Life of a photo",
    "Privacy and image analysis happen in the production ingest pipeline.",
    [
        (
            "Validate the upload",
            "Check team, pass owner, JPEG, SHA-256 and time window. GPS issues are flags, not dropped photos.",
        ),
        (
            "Quarantine the original",
            "Keep the original private. Queue an ingest_photo job; repeated uploads are idempotent.",
        ),
        (
            "Detect and redact",
            "Apply EXIF orientation and strip metadata. YOLO11s finds dogs, people and vehicles; redact people and vehicles.",
        ),
        (
            "Check privacy again",
            "If people were detected, re-run detection on the blurred image and check for unredacted person regions.",
        ),
        (
            "Crop and embed dogs",
            "Crop from the blurred image. Score quality; extract a 384-value DINOv2 embedding and colour histogram.",
        ),
        (
            "Save safe outputs",
            "Store the blurred image, crops and detections. Delete the original after successful processing.",
        ),
    ],
    "Sources: routers/passes.py; notchcount_pipeline/ingest.py; notchcount_worker/ingest.py.",
    (
        "If the privacy check fails",
        "Mark the photo failed and store no processed output. The original remains in private quarantine; it is never served.",
        ORANGE,
    ),
)

grid_flow(
    "04",
    "Dog matching and ear review",
    "Appearance suggests candidates; human labels and model uncertainty remain part of the result.",
    [
        (
            "Represent each sighting",
            "Use the dog crop embedding, colour histogram, time and position along the route.",
        ),
        (
            "Find candidate pairs",
            "Filter by route distance, time and visual similarity. Score P(same dog) with a logistic match model.",
        ),
        (
            "Collect human labels",
            "Review uncertain pairs: same, different or unsure. Keep individual answers for agreement checks.",
        ),
        (
            "Learn from the labels",
            "Train team-specific match and ear models. Store model versions and held-out evaluation metrics.",
        ),
        (
            "Call the ear status",
            "Predict notched, not notched or not visible. Human ear labels inform decisions; hidden ears stay unknown.",
        ),
        (
            "Build individuals",
            "Cluster sightings within a walk and assign across walks. Sample uncertain matches for the estimator.",
        ),
    ],
    "Sources: pipeline/match.py, notch.py, assign.py; worker/analysis.py; notchcount_stats/assignment.py.",
    (
        "Before enough training data exists",
        "Matching uses a labelled uncalibrated prior. Without a trained ear model, the worker skips automatic notch scoring.",
    ),
)

im = canvas(
    "05",
    "How the estimate is calculated",
    "Illustration uses the documented engine check: real photos with a transformed second pass.",
    "Sources: docs/ENGINE_CHECK.md; notchcount_stats/propagate.py, closed.py and assignment.py.",
)
for x, label, value, desc in [
    (80, "WALK 1", "12", "distinct detected dogs"),
    (860, "WALK 2", "12", "distinct detected dogs"),
    (1640, "SEEN ON BOTH", "9", "matched dogs"),
]:
    box(im, (x, 350, 680, 240), label, "", fill=GREEN if x == 1640 else WHITE, title_size=30)
    txt(im, (x + 30, 415), value, 85, bold=True)
    txt(im, (x + 175, 470), desc, 29, MUTED, width=470)
txt(im, (90, 650), "Chapman total = ((n1 + 1) × (n2 + 1) / (m2 + 1)) − 1", 47, bold=True)
txt(im, (90, 725), "For these counts: ((12 + 1) × (12 + 1) / (9 + 1)) − 1 = 15.9 dogs", 36, MUTED)
box(
    im,
    (80, 840, 680, 310),
    "1. Sample uncertainty",
    "Default: 2,000 draws of plausible dog matches and ear status calls.",
    fill=PALE,
)
box(
    im,
    (860, 840, 680, 310),
    "2. Draw outcomes",
    "Population: Chapman + Chao log-normal. Sterilised share: Jeffreys Beta draws.",
)
box(
    im,
    (1640, 840, 680, 310),
    "3. Summarise",
    "Return median and 95% ranges. Store the seed, data hash and code version.",
)
arrow(im, [(770, 995), (850, 995)])
arrow(im, [(1550, 995), (1630, 995)])
callout(
    im,
    1210,
    "Recorded engine-check result",
    "About 15.9 dogs (95% range 15.1–21.6). No sterilised share was reported because that check had no ear labels.",
)
save(im, "05-estimation-logic.png")

grid_flow(
    "06",
    "Offline capture and upload",
    "The browser saves the photo locally before attempting to reach the server.",
    [
        (
            "Capture + resize",
            "Create a JPEG at up to 1,600 px long edge. Record time, shot type and available GPS; hash the image.",
        ),
        (
            "Save in IndexedDB",
            "Store the photo and pass locally. The camera alternates side and head shots for each dog.",
        ),
        (
            "Allow an undo",
            "Wait 8 seconds before upload eligibility. A queued capture can be removed during that window.",
        ),
        (
            "Sync when connected",
            "Create the server pass if needed. Upload eligible photos in order; retry temporary failures.",
        ),
        (
            "Handle server responses",
            "Success: mark uploaded and release the local blob. Permanent rejection: retain an error status.",
        ),
        (
            "Finish the pass",
            "After the walker ends the pass, wait until no photos are queued, then sync its end time.",
        ),
    ],
    "Sources: apps/web/src/lib/queue.ts, image.ts; routes/app/capture/[survey]/[pass]/+page.svelte.",
    (
        "Connection can come and go",
        "An online event and a 15-second capture-page timer trigger sync. SHA-256 and server idempotency prevent duplicate photo records.",
    ),
)

im = canvas(
    "07",
    "Where the data lives",
    "A simplified relationship map of the core database records.",
    "Source: services/api/src/notchcount_api/db/models.py. Arrows mean ownership or references; this is not the full schema.",
)
for x, title, body in [
    (80, "Teams + people", "users • team_members\nroles and memberships"),
    (860, "Routes + surveys", "routes → surveys\nfixed geometry and time window"),
    (1640, "Passes + photos", "passes → photos\nobserver, time, GPS and hashes"),
]:
    box(im, (x, 350, 680, 265), title, body, fill=GREEN if x == 80 else WHITE)
arrow(im, [(770, 480), (850, 480)])
arrow(im, [(1550, 480), (1630, 480)])
for x, title, body in [
    (80, "Match pairs + labels", "match_pairs references two detections\npair_labels stores each answer"),
    (860, "Ear calls + labels", "notch_calls → detection\nnotch_labels stores each answer"),
    (1640, "Dog detections", "detections → photo\nbounding box, embedding, quality"),
]:
    box(im, (x, 735, 680, 265), title, body, body_size=30)
arrow(im, [(1980, 625), (1980, 725)])
arrow(im, [(1640, 680), (420, 680), (420, 725)])
arrow(im, [(1980, 650), (1200, 650), (1200, 725)])
for x, title, body in [
    (80, "Results + individuals", "estimates • individuals • sightings\nresults link back to a survey"),
    (860, "Cases + history", "cases → survey\ncase_events → case"),
    (1640, "Supporting records", "jobs • blobs • model_versions\nqueues, image data and fitted models"),
]:
    box(im, (x, 1080, 680, 245), title, body, fill=PALE, body_size=29, title_size=36)
save(im, "07-database-logic.png")

grid_flow(
    "08",
    "From estimate to case file",
    "A saved estimate is the common source for the public report, PDF and case draft.",
    [
        (
            "Store the estimate",
            "Persist results, method, input hash, random seed and version information for reproducibility.",
        ),
        (
            "Publish route results",
            "Public report and PDF show totals and ranges. Dog locations remain in the team view.",
        ),
        (
            "Create the case draft",
            "Agentboxd creates an inbox and draft with the draft-only key. The draft quotes a stored estimate.",
        ),
        (
            "Admin approves",
            "A signed-in team admin chooses Approve and send. The stored draft content hash is passed to the send API.",
        ),
        (
            "Send + record history",
            "The approval path uses the send key. Approval and send events are recorded in the case timeline.",
        ),
        (
            "Receive official replies",
            "Verify signed webhook events. Store replies as untrusted text; suspicious replies are held.",
        ),
    ],
    "Sources: reporting.py; routers/reports.py; routers/cases.py; filing/agentboxd.py.",
    (
        "The sending gate",
        "Drafting and reporting never send email by themselves. Sending requires the explicit admin approval action.",
    ),
)

# Preserve original app screenshots without resizing or altering their pixels.
for src in sorted((ROOT / "docs/screens").glob("*.png")):
    shutil.copy2(src, SCREENS / src.name)
shutil.copy2(ROOT / "docs/estimator_validation.png", EVIDENCE / "estimator-validation.png")

# Run the actual ONNX pipeline on repository fixtures for fresh technical evidence.
import numpy as np  # noqa: E402

from notchcount_pipeline.detect import Coco  # noqa: E402
from notchcount_pipeline.ingest import Models, decode, process  # noqa: E402
from notchcount_pipeline.privacy import expand, unblurred_person_boxes  # noqa: E402

models = Models.load(ROOT / "models/cache")
fixture = ROOT / "packages/pipeline/tests"
dog = process((fixture / "fixture_dog.jpg").read_bytes(), models)
people_raw = (fixture / "fixture_people.jpg").read_bytes()
people = process(people_raw, models)
before = [b for b in models.detector(decode(people_raw)) if b.cls == Coco.PERSON]
stored = decode(people.blurred_jpeg)
mask = np.zeros(stored.shape[:2], dtype=bool)
for b in before:
    x1, y1, x2, y2 = expand(b, stored.shape[1], stored.shape[0])
    mask[y1:y2, x1:x2] = True
remaining = unblurred_person_boxes(models.detector(stored), mask)
assert len(dog.dogs) >= 1 and not remaining
(EVIDENCE / "processed-dog.jpg").write_bytes(dog.blurred_jpeg)
(EVIDENCE / "privacy-redacted.jpg").write_bytes(people.blurred_jpeg)
(EVIDENCE / "dog-crop.jpg").write_bytes(dog.dogs[0].jpeg)
metrics = {
    "dog_count": len(dog.dogs),
    "dog_detection_confidence": float(dog.dogs[0].box.conf),
    "embedding_dimensions": len(dog.dogs[0].embedding),
    "quality": float(dog.dogs[0].quality),
    "usable": bool(dog.dogs[0].usable),
    "persons_blurred": people.persons_blurred,
    "vehicles_blurred": people.vehicles_blurred,
    "unredacted_person_regions_after_check": len(remaining),
    "processed_photo_exif_fields": len(Image.open(io.BytesIO(people.blurred_jpeg)).getexif()),
    "model_version": models.version,
    "source": "Repository fixture images, real local ONNX inference. Not field-study validation.",
}
(OUT / "pipeline-check.json").write_text(json.dumps(metrics, indent=2) + "\n")


def paste_fit(im, path, rect):
    x, y, w, h = rect
    with Image.open(path) as src:
        scaled = ImageOps.contain(src.convert("RGB"), (w, h), Image.Resampling.LANCZOS)
    im.paste(scaled, (x + (w - scaled.width) // 2, y + (h - scaled.height) // 2))


im = canvas(
    "09",
    "Actual dog detection and crop",
    "Fresh output from the installed YOLO11s + DINOv2 pipeline, using a repository sample.",
    "Photo: “Street Dog 03” by Slyronit, Wikimedia Commons, CC BY-SA 4.0. Attribution and links are in README.md in this pack.",
)
paste_fit(im, EVIDENCE / "processed-dog.jpg", (80, 360, 1000, 770))
paste_fit(im, EVIDENCE / "dog-crop.jpg", (1240, 360, 700, 600))
arrow(im, [(1095, 680), (1220, 680)])
txt(im, (90, 1160), "Processed photo", 37, bold=True)
txt(im, (1250, 1000), "Detected dog crop", 37, bold=True)
txt(
    im,
    (1250, 1070),
    f"Confidence: {metrics['dog_detection_confidence']:.1%}  •  Usable: {metrics['usable']}",
    31,
    MUTED,
)
txt(im, (1250, 1130), "384-value appearance embedding", 31, MUTED)
callout(
    im,
    1220,
    "What this demonstrates",
    "The pipeline produces a real crop, quality score and feature vector from a photo. A single photo does not establish field matching accuracy.",
)
save(im, "09-real-dog-pipeline.png", EVIDENCE)

im = canvas(
    "10",
    "Actual privacy processing",
    "Real local inference: people and vehicles are redacted before processed images are stored.",
    "Sample: bus.jpg from Ultralytics assets, AGPL-3.0. The source link is in README.md in this pack.",
)
paste_fit(im, EVIDENCE / "privacy-redacted.jpg", (80, 345, 1150, 980))
box(
    im,
    (1370, 360, 950, 260),
    "Redacted objects",
    f"{people.persons_blurred} people\n{people.vehicles_blurred} vehicles",
    fill=GREEN,
)
box(
    im,
    (1370, 680, 950, 260),
    "Privacy verification",
    f"{len(remaining)} unredacted person regions\n{metrics['processed_photo_exif_fields']} EXIF metadata fields",
)
box(
    im,
    (1370, 1000, 950, 280),
    "Successful ingest",
    "Store blurred image and dog crops.\nDelete the quarantined original.",
    fill=PALE,
)
save(im, "10-real-privacy-pipeline.png", EVIDENCE)

LABELS = [
    ("landing", "Landing page"),
    ("signed-out", "Sign in"),
    ("home", "Team home"),
    ("survey", "Survey dashboard"),
    ("label-pairs", "Dog-pair labels"),
    ("label-ears", "Ear-notch labels"),
    ("review", "Review queue"),
    ("report", "Public report"),
    ("case", "Case file"),
    ("team", "Team management"),
    ("field-card", "Field protocol"),
    ("health", "System health"),
]


def screen_sheet(mobile=False):
    im = canvas(
        "SCREENS",
        "Phone screens" if mobile else "Desktop screens",
        "Existing full-size captures are included separately; this sheet previews their first viewport.",
        "Recorded demo screenshots, 23 Oct 2026. Real dog photos; second walk simulated. These are saved captures, not fresh live-site checks.",
        size=(2400, 2080),
    )
    d = ImageDraw.Draw(im)
    for i, (slug, label) in enumerate(LABELS):
        x = 80 + (i % 4) * 580
        y = 345 + (i // 4) * 525
        d.rounded_rectangle((x, y, x + 500, y + 475), 20, fill=WHITE)
        src = SCREENS / f"{slug}-{'375' if mobile else '1280'}.png"
        with Image.open(src) as s:
            thumb = s.crop((0, 0, s.width, min(s.height, 812 if mobile else 900)))
            thumb = ImageOps.contain(thumb, (460, 380), Image.Resampling.LANCZOS)
            im.paste(thumb, (x + (500 - thumb.width) // 2, y + 15))
        txt(im, (x + 22, y + 415), label, 28, bold=True)
    save(im, "00-phone-screens.png" if mobile else "00-desktop-screens.png", OUT)


screen_sheet()
screen_sheet(True)

im = canvas(
    "OFFLINE",
    "Offline capture and reconnect",
    "Fresh screenshots of the actual app UI. Mock API; synthetic browser-camera signal; no production writes.",
    "Verified locally: 3 captures queued offline, then 3 uploads after reconnect. Side / head / side shots count as 2 dogs.",
    size=(2400, 1700),
)
for x, slug, label in [
    (190, "capture-ready-375", "1. Camera ready"),
    (960, "capture-offline-375", "2. Three shots offline"),
    (1730, "capture-synced-375", "3. All uploaded"),
]:
    path = SCREENS / (slug + ".png")
    if path.exists():
        paste_fit(im, path, (x, 360, 480, 1040))
    txt(im, (x, 1450), label, 35, bold=True)
arrow(im, [(710, 880), (920, 880)])
arrow(im, [(1480, 880), (1690, 880)])
save(im, "00-offline-capture-demo.png", OUT)

im = canvas(
    "REVIEW",
    "Human review in the app",
    "Fresh local UI captures with mock review tasks and a real repository dog crop.",
    "Demo tasks only: the pair repeats the same fixture photo. Ear status is unanswered; this is a UI example, not an ear-model accuracy result.",
    size=(2400, 1500),
)
for x, mode, label in [
    (80, "pairs", "Same dog, different dog, or not sure"),
    (1240, "ears", "Notched, not notched, or ear not visible"),
]:
    path = SCREENS / f"label-{mode}-demo-1280.png"
    if path.exists():
        paste_fit(im, path, (x, 350, 1080, 800))
    txt(im, (x + 12, 1200), label, 35, bold=True, width=1050)
save(im, "00-human-review-demo.png", OUT)

readme = """# NotchCount — important project images

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
"""
(OUT / "README.md").write_text(readme)
images = sorted(p for p in OUT.rglob("*") if p.suffix.lower() in {".png", ".jpg"})
for path in images:
    with Image.open(path) as check:
        check.verify()
archive = ROOT / "docs/NotchCount-project-images.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            z.write(p, Path("NotchCount-project-images") / p.relative_to(OUT))
print(
    json.dumps(
        {"images": len(images), "archive": str(archive), "output": str(OUT), "pipeline": metrics}, indent=2
    )
)
