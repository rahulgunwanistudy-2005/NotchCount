"""Turn a stored estimate into the words and the PDF an official reads. Every number printed
here is read from the estimate's stored results; nothing is computed or rounded differently
in the email, the web page and the PDF."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Headline:
    population: str | None
    share: str | None
    deficit: str | None
    note: str | None


def _n(v: float | None) -> str:
    return "?" if v is None else f"{round(v):d}"


def _p(v: float | None) -> str:
    return "?" if v is None else f"{round(v * 100):d}%"


def headline(results: dict[str, Any]) -> Headline:
    pop = results.get("population")
    share = results.get("share")
    deficit = results.get("deficit")
    single = results.get("single_pass")
    note = None
    population = None
    if pop:
        population = f"About {_n(pop['median'])} dogs use this route ({_n(pop['low'])} to {_n(pop['high'])})."
    elif single:
        population = f"{single['individuals']} different dogs were seen on one walk of the route."
        note = "Walk the route again on another morning to estimate how many dogs use it."
    elif results.get("counts"):
        population = None
        note = "Not enough dogs were matched between the walks to estimate the total. Walk the route again."
    share_text = None
    if share:
        share_text = f"{_p(share['median'])} are sterilised ({_p(share['low'])} to {_p(share['high'])})."
    elif single and single["share"]["share"] is not None:
        s = single["share"]
        share_text = f"{_p(s['share'])} are sterilised ({_p(s['low'])} to {_p(s['high'])})."
    deficit_text = None
    if deficit:
        k = round(deficit["median"])
        noun = "sterilisation" if k == 1 else "sterilisations"
        deficit_text = (
            f"Reaching 70% needs about {k} more {noun} ({_n(deficit['low'])} to {_n(deficit['high'])})."
        )
    return Headline(population, share_text, deficit_text, note)


def method_lines(results: dict[str, Any], method: str) -> list[str]:
    lines = []
    passes = results.get("passes", [])
    if passes:
        days = ", ".join(datetime.fromisoformat(p["started_at"]).strftime("%d %b") for p in passes)
        times = {1: "once", 2: "twice"}.get(len(passes), f"{len(passes)} times")
        lines.append(f"The same route was walked {times} at the same morning hour ({days}).")
    lines.append(
        "Every free-roaming dog seen from the route was photographed. Software matched dogs across walks "
        "from their appearance, and team members checked every uncertain match and ear."
    )
    if method == "two_pass_sampled_chapman":
        c = results.get("counts", {})
        lines.append(
            f"Dogs seen on walk 1: {c.get('n1')}. On walk 2: {c.get('n2')}. Seen on both: {c.get('m2')}. "
            "The total comes from the Chapman mark-resight estimator; the range is a 95% interval that also "
            f"carries the uncertainty of the matching ({results.get('replicates')} simulations)."
        )
    ps = results.get("point_share") or (results.get("single_pass") or {}).get("share")
    if ps:
        lines.append(
            f"In the best-guess matching, {ps['notched']} of the {ps['with_visible_ear']} dogs whose ear could be "
            f"seen carried the sterilisation ear-notch, and {ps['excluded_not_visible']} dogs with hidden ears are "
            "left out of the share. The share above is the middle of the simulations, which also allow for ear "
            "calls the software was unsure about."
        )
    return lines


ASSUMPTIONS = (
    "The dogs on the route were the same population on both mornings (walks one or two days apart).",
    "Some dogs are easier to see than others; this makes the total more likely too low than too high.",
    "The estimate is for dogs using this route, not the whole ward.",
    "An ear-notch shows the dog went through the sterilisation programme; it does not prove current rabies "
    "vaccination. The 70% line is a benchmark from rabies-control studies.",
)


def render_pdf(
    *,
    title: str,
    route_name: str,
    city: str,
    results: dict[str, Any],
    method: str,
    code_version: str,
    data_hash: str | None,
    created_at: datetime,
    report_url: str | None,
) -> bytes:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    ink, teal, fog = HexColor("#1F2B38"), HexColor("#0B6B66"), HexColor("#5F6B73")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=ink, spaceAfter=4)
    big = ParagraphStyle(
        "big", fontName="Helvetica-Bold", fontSize=14, leading=19, textColor=ink, spaceAfter=3
    )
    body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10.5, leading=14.5, textColor=ink, spaceAfter=4
    )
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, leading=11, textColor=fog)
    h2 = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=teal, spaceBefore=8
    )

    hl = headline(results)
    story: list[Any] = [
        Paragraph(title, h1),
        Paragraph(f"{route_name}, {city}. Survey by residents with NotchCount.", body),
        Spacer(1, 4 * mm),
    ]
    for line in (hl.population, hl.share, hl.deficit):
        if line:
            story.append(Paragraph(line, big))
    if hl.note:
        story.append(Paragraph(hl.note, body))
    for problem in results.get("comparability_problems", []):
        story.append(Paragraph(problem, body))
    story += [Paragraph("How we counted", h2), *[Paragraph(x, body) for x in method_lines(results, method)]]
    story += [Paragraph("What we assumed", h2), *[Paragraph(x, body) for x in ASSUMPTIONS]]
    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            f"Computed {created_at:%d %b %Y %H:%M} UTC by {code_version}, method {method}, data hash "
            f"{(data_hash or 'none')[:16]}. Photos of people and vehicles were blurred before storage; individual "
            "dog locations are not published.",
            small,
        ),
    ]
    if report_url:
        story.append(Paragraph(f"Full report: {report_url}", small))
    buf = io.BytesIO()
    SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="NotchCount",
    ).build(story)
    return buf.getvalue()


def draft_email(
    *,
    officer: str,
    route_name: str,
    city: str,
    results: dict[str, Any],
    method: str,
    report_url: str,
    team_name: str,
) -> tuple[str, str]:
    hl = headline(results)
    lines = [
        f"Dear {officer},",
        "",
        f"We are residents and students in {city}. We counted the street dogs on {route_name} using a "
        "repeat-walk photo survey, and checked each dog's ear for the sterilisation notch.",
        "",
    ]
    lines += [x for x in (hl.population, hl.share, hl.deficit, hl.note) if x]
    lines += [
        "",
        *method_lines(results, method),
        "",
        f"The full report, with how it was made and its limits, is here: {report_url}",
        "A one-page PDF is attached.",
        "",
        "Could you tell us whether sterilisation is planned for this area, and how coverage is "
        "recorded for this ward?",
        "",
        "Thank you,",
        team_name,
    ]
    subject = f"Street dog sterilisation coverage on {route_name}, {city}"
    return subject, "\n".join(lines)
