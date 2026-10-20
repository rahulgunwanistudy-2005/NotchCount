# NotchCount design brief

Read with `design/frontend-design/SKILL.md`. That skill sets the process (plan, critique against generic defaults, build, critique by screenshot). This brief supplies the subject, the starting plan and the specific rules. The agent may improve the plan after its own critique, but must log every change and the reason in `docs/DECISIONS.md`.

## Subject, audience, job

- **Subject:** free-roaming dogs on Indian residential lanes at dawn; the ear-notch a vet cuts during sterilisation; a walk repeated on two mornings; a number an official has to answer.
- **Audience:** teenage walkers and residents on cheap Android phones in morning sun; a ward officer reading a one-page report; hackathon judges who will open it on a laptop.
- **Primary job:** make counting fast and trustworthy in the field, and make the result impossible to wave away: a number, its range, and how it was made.

## Starting plan

### Colour (light theme first: field use is outdoors in daylight)

| Name | Hex | Role |
|---|---|---|
| Limewash | #EEF2EF | Page background; the cool blue-white of whitewashed walls, not cream |
| Ink slate | #1F2B38 | Text, shutter, primary buttons (14.4:1 on white) |
| Notch teal | #0B6B66 | Sterilised dogs, confirmed states (5.6:1 on Limewash) |
| Sodium | #E8A317 | Not sterilised, needs action. Fill only, always with Ink slate text on it (6.6:1); never as text colour |
| Survey blue | #2F5D9E | Links, focus ring, selected route |
| Fog | #8A969E / text #5F6B73 | Ear not visible, unknown; always paired with a hatch pattern so it never relies on colour |

Data colours must pass a deuteranopia and protanopia simulation check; teal versus sodium does, but verify. A dark theme is optional and comes last.

### Type

- **Display and numbers:** Anek (Latin and Devanagari variable families, with a width axis). Use the condensed width for large counts and interval figures; tabular figures for every number that updates.
- **Body and UI:** Mukta (Latin and Devanagari).
- Verify both are available on Google Fonts with Devanagari subsets before committing; if not, pick another pair that covers both scripts and log it.
- Scale: 1.25 ratio from a 17 px base on phones, 18 px on desktop. Body line length under 70 characters. Hindi lines get 10% more line-height.

### The one bold thing: the notch

The brand mark is a filled circle with a small V cut from its upper-left edge, the shape of an ear-notch. Spend boldness only here and in one animation:

- **Structural meaning:** a sighting tile gets the notch-cut corner only when that dog is a confirmed individual. Unconfirmed tiles are plain rectangles. The cut encodes state; it is never decoration.
- **The orchestrated moment:** on the report page (and the landing page, using the team's real data), dots from pass 1 drop onto a straightened strip of the route, then pass 2's dots drop below; matched dogs join with short arcs; the population figure and its range bar resolve last. About 2.5 seconds, once. With reduced motion, show the final state.

Everything else stays quiet: flat surfaces, hierarchy from type and spacing, borders only where they separate interactive regions.

### Layout and screens

Left-aligned throughout. Mobile-first for capture and review; desktop two-column for report and case file.

**Capture (phone, one-handed):**

```
+----------------------------------+
| Pass 1 of 2        Offline: 3 queued
| Gali No. 4 loop    GPS ±6 m      |
|                                  |
|        [ live camera view ]      |
|                                  |
|  Side shot  ->  Head shot        |  (step indicator for the current dog)
|                                  |
|  23 dogs this pass               |
|            (  SHUTTER  )         |  (Ink slate, 76 px, bottom third)
|  End pass                Undo    |
+----------------------------------+
```

**Review (phone or laptop):**

```
+-------------------+-------------------+
|   crop A          |   crop B          |
|   Pass 1, 06:52   |   Pass 2, 06:49   |
|   120 m apart along the route         |
+-------------------+-------------------+
| Same dog (S)  Different (D)  Not sure (N)
| 14 left. Each answer tightens the estimate.
+---------------------------------------+
```

**Report (desktop, two columns; stacks on phone):**

```
+----------------------------+----------------------+
| About 61 dogs use this     | [route strip with    |
| route (56 to 74).          |  pass 1 / pass 2     |
|                            |  dots and arcs]      |
| 59% are sterilised         |                      |
| (45% to 72%).              |                      |
| Reaching 70% needs about   |                      |
| 7 more sterilisations.     |                      |
+----------------------------+----------------------+
| How we counted   What we assumed   What could be wrong
| Download PDF     Send to ward officer
+---------------------------------------------------+
```

The numbers above come from the worked example in BIBLE 3.7; the real report uses the team's data.

**Case file:** a numbered timeline (this content really is a sequence: drafted, approved, sent, replied), the draft rendered as the officer will see it, one primary button "Approve and send", and the approver's name recorded under it.

**Landing page:** hero opens with the characteristic thing: a close photo of a real notched ear from the team's route (with permission, no people), the line "Count the dogs on your street. Find out if sterilisation is really happening.", and the orchestrated animation below it built from the team's data. Then three short sections: how it works (a real sequence, numbered), what the team found, how to run it on your street.

## Rules

- A number is never shown without its range, and the range is never hidden because it is wide.
- No all-caps labels, no eyebrow labels above headings, no middle-dot meta strings, no arrow glyphs appended to buttons, no monospace for data labels, no gradient washes, no identical rounded card grids, no default component-kit look.
- Sentence case. Buttons say exactly what happens: "End pass", "Same dog", "Approve and send". The toast after "Approve and send" says "Sent to [officer]".
- Errors say what happened and what to do: "No GPS fix. Stand still for 10 seconds or move away from tall walls." Empty states invite the next action.
- Field screens readable in direct sun: minimum 17 px text, 4.5:1 contrast everywhere, 7:1 for the capture status line.
- Touch targets at least 44 px; the shutter 76 px; nothing the walker must tap sits in the top third of the phone screen.
- Icons always with a text label on field screens (low-literacy users, Hindi readers).
- Hindi strings are written or checked by a Hindi-speaking team member (HUMAN); never ship machine-translated Hindi unchecked.
- Respect `prefers-reduced-motion`; motion only for the orchestrated moment and for feedback on user actions (capture flash, match confirmed).

## References

- Use the Mobbin MCP to look at real camera-capture, photo-review and verification flows before building those screens; note in `docs/DECISIONS.md` which patterns you adopted and why.
- Maps: MapLibre GL with a free vector tile source whose terms allow this use (verify); restyle the basemap to Limewash and Fog so the route and dots carry the colour.

## Self-critique checklist (run per screen, at 375 px and 1280 px)

1. Would this screen look the same for any other app? If yes, what from the subject is missing?
2. Is the notch used only where it means something?
3. Can a walker use it one-handed in sunlight with a dog moving?
4. Is every number paired with its range?
5. Remove one accessory.
