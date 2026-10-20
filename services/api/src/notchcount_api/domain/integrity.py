"""Pass-integrity rules (SESSION_PROMPT P5, FIELD_PROTOCOL). Pure functions, unit-tested.

Hard rules reject a photo; soft rules attach a flag that reviewers and the report can see.
Nothing is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CLOCK_SKEW = timedelta(minutes=2)
FUTURE_SKEW = timedelta(minutes=5)


class PhotoRejected(Exception):
    """Message is shown to the walker."""


@dataclass(frozen=True, slots=True)
class PassWindow:
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class PhotoCheck:
    flags: list[str] = field(default_factory=list)


def check_photo(
    window: PassWindow,
    taken_at: datetime,
    received_at: datetime,
    accuracy_m: float | None,
    has_location: bool,
    inside_corridor: bool | None,
    *,
    poor_accuracy_m: float,
    grace_after_end: timedelta,
) -> PhotoCheck:
    if taken_at.tzinfo is None:
        raise PhotoRejected("Photo time has no time zone. Update the app and try again.")
    if taken_at > received_at + FUTURE_SKEW:
        raise PhotoRejected("Photo time is in the future. Turn on automatic date and time on the phone.")
    if taken_at < window.started_at - CLOCK_SKEW:
        raise PhotoRejected("Photo was taken before this pass started, so it cannot count for it.")
    if window.ended_at is not None and taken_at > window.ended_at + grace_after_end:
        raise PhotoRejected("Photo was taken after this pass ended, so it cannot count for it.")
    flags: list[str] = []
    if not has_location:
        flags.append("no_gps")
    elif accuracy_m is None or accuracy_m > poor_accuracy_m:
        flags.append("poor_gps")
    if has_location and inside_corridor is False:
        flags.append("outside_corridor")
    return PhotoCheck(flags)


def start_offset_minutes(started_at: datetime, window_local: time, tz: str) -> float:
    """Minutes between when a pass started and the survey's agreed local start time."""
    local = started_at.astimezone(ZoneInfo(tz))
    agreed = datetime.combine(local.date(), window_local, tzinfo=local.tzinfo)
    return (local - agreed).total_seconds() / 60.0


def pass_start_flags(started_at: datetime, window_local: time, tz: str, tolerance_min: int) -> list[str]:
    offset = start_offset_minutes(started_at, window_local, tz)
    return [] if abs(offset) <= tolerance_min else ["start_outside_window"]


@dataclass(frozen=True, slots=True)
class PassSummary:
    pass_no: int
    started_at: datetime
    ended_at: datetime | None
    route_id: str


def comparability_problems(
    passes: list[PassSummary], window_local: time, tz: str, tolerance_min: int
) -> list[str]:
    """Reasons the passes cannot be combined into one population estimate (empty = fine)."""
    problems: list[str] = []
    if len({p.route_id for p in passes}) > 1:
        problems.append("The passes were walked on different routes. Walk the same route each time.")
    for p in passes:
        if p.ended_at is None:
            problems.append(f"Pass {p.pass_no} has not been ended yet.")
        if abs(start_offset_minutes(p.started_at, window_local, tz)) > tolerance_min:
            problems.append(
                f"Pass {p.pass_no} started more than {tolerance_min} minutes away from the agreed "
                f"start time {window_local:%H:%M}. Dogs move through the day, "
                "so the counts are not comparable."
            )
    days: list[date] = sorted({p.started_at.astimezone(ZoneInfo(tz)).date() for p in passes})
    if len(days) != len(passes):
        problems.append("Two passes were walked on the same day. Walk each pass on a different morning.")
    elif days and (days[-1] - days[0]).days > len(passes) + 1:
        problems.append(
            "The passes are too far apart. Walk them on mornings close together so the dogs are the same."
        )
    return problems
