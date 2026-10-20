"""Case file and filing. A draft is created with the draft-only key; nothing is sent until a
signed-in team admin presses Approve, which is the only code path that uses the send key."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.config import Settings
from notchcount_api.db.models import (
    Case,
    CaseEvent,
    CaseEventKind,
    Estimate,
    Role,
    RouteRow,
    Survey,
    Team,
    User,
)
from notchcount_api.deps import DbDep, SettingsDep, UserDep, require_role
from notchcount_api.filing.agentboxd import (
    AgentboxdClient,
    Attachment,
    FilingError,
    should_hold,
    verify_webhook,
)
from notchcount_api.reporting import draft_email, render_pdf
from notchcount_api.routers.setup import survey_team

router = APIRouter(tags=["cases"])
webhooks = APIRouter(tags=["webhooks"])

# Tests inject a fake Agentboxd here; production leaves it None.
TRANSPORT: httpx.AsyncBaseTransport | None = None
MAX_WEBHOOK_BYTES = 256 * 1024


class CaseCreate(BaseModel):
    authority_name: str = Field(min_length=2, max_length=200)
    authority_email: EmailStr


class DraftCreate(BaseModel):
    estimate_id: uuid.UUID


class EventOut(BaseModel):
    id: uuid.UUID
    kind: CaseEventKind
    payload: dict[str, Any]
    actor_name: str | None
    created_at: datetime


class CaseOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    authority_name: str
    authority_email: str
    status: str
    inbox_address: str | None
    report_url: str | None
    events: list[EventOut]


async def _case_for(
    db: AsyncSession, user: User, case_id: uuid.UUID, role: Role
) -> tuple[Case, Survey, uuid.UUID]:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    found = await survey_team(db, case.survey_id)
    assert found is not None
    await require_role(db, user, found[1], role)
    return case, found[0], found[1]


def report_url(settings: Settings, survey: Survey) -> str | None:
    return f"{settings.public_base_url}/r/{survey.public_slug}" if survey.public_slug else None


async def _case_out(db: AsyncSession, settings: Settings, case: Case, survey: Survey) -> CaseOut:
    rows = (
        await db.execute(
            select(CaseEvent, User.display_name)
            .outerjoin(User, User.id == CaseEvent.actor_id)
            .where(CaseEvent.case_id == case.id)
            .order_by(CaseEvent.created_at)
        )
    ).all()
    inbox = next((e.payload.get("inbox_address") for e, _ in rows if e.payload.get("inbox_address")), None)
    return CaseOut(
        id=case.id,
        survey_id=case.survey_id,
        authority_name=case.authority_name,
        authority_email=case.authority_email,
        status=case.status,
        inbox_address=inbox,
        report_url=report_url(settings, survey),
        events=[
            EventOut(id=e.id, kind=e.kind, payload=e.payload, actor_name=n, created_at=e.created_at)
            for e, n in rows
        ],
    )


@router.post("/surveys/{survey_id}/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    survey_id: uuid.UUID, body: CaseCreate, user: UserDep, db: DbDep, settings: SettingsDep
) -> CaseOut:
    found = await survey_team(db, survey_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    survey, team_id = found
    await require_role(db, user, team_id, Role.ADMIN)
    case = Case(
        survey_id=survey_id, authority_name=body.authority_name, authority_email=str(body.authority_email)
    )
    db.add(case)
    await db.commit()
    return await _case_out(db, settings, case, survey)


@router.get("/surveys/{survey_id}/cases", response_model=list[CaseOut])
async def list_cases(survey_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep) -> list[CaseOut]:
    found = await survey_team(db, survey_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    await require_role(db, user, found[1], Role.REVIEWER)
    cases = (
        await db.execute(select(Case).where(Case.survey_id == survey_id).order_by(Case.created_at))
    ).scalars()
    return [await _case_out(db, settings, c, found[0]) for c in cases]


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(case_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep) -> CaseOut:
    case, survey, _ = await _case_for(db, user, case_id, Role.REVIEWER)
    return await _case_out(db, settings, case, survey)


@router.post("/cases/{case_id}/drafts", response_model=CaseOut)
async def create_draft(
    case_id: uuid.UUID, body: DraftCreate, user: UserDep, db: DbDep, settings: SettingsDep
) -> CaseOut:
    case, survey, team_id = await _case_for(db, user, case_id, Role.ADMIN)
    est = (
        await db.execute(
            select(Estimate).where(Estimate.id == body.estimate_id, Estimate.survey_id == survey.id)
        )
    ).scalar_one_or_none()
    if est is None or est.status != "done" or est.results is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Run an estimate first; the draft quotes its numbers.")
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one()
    route = (await db.execute(select(RouteRow).where(RouteRow.id == survey.route_id))).scalar_one()
    if survey.public_slug is None:
        survey.public_slug = secrets.token_urlsafe(9)
    url = report_url(settings, survey)
    assert url is not None
    subject, text = draft_email(
        officer=case.authority_name,
        route_name=route.name,
        city=team.city,
        results=est.results,
        method=est.method,
        report_url=url,
        team_name=team.name,
    )
    pdf = render_pdf(
        title=f"Street dogs on {route.name}",
        route_name=route.name,
        city=team.city,
        results=est.results,
        method=est.method,
        code_version=est.code_version,
        data_hash=est.data_hash,
        created_at=est.created_at,
        report_url=url,
    )
    key = settings.agentboxd_draft_key.get_secret_value() if settings.agentboxd_draft_key else None
    try:
        async with AgentboxdClient(settings.agentboxd_base_url, key, TRANSPORT) as ab:
            inbox = await ab.ensure_inbox(f"case-{case.id}", f"{team.name} case")
            draft = await ab.create_draft(
                str(inbox["id"]),
                to=[case.authority_email],
                subject=subject,
                text=text,
                html=None,
                attachments=[
                    Attachment("notchcount-report.pdf", "application/pdf", base64.b64encode(pdf).decode())
                ],
                idempotency_key=f"draft-{case.id}-{est.id}",
            )
    except FilingError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    case.agentboxd_inbox_id = str(inbox["id"])
    content_sha = draft.get("content_sha256") or hashlib.sha256((subject + "\n" + text).encode()).hexdigest()
    db.add(
        CaseEvent(
            case_id=case.id,
            kind=CaseEventKind.DRAFT,
            actor_id=user.id,
            external_id=f"draft:{draft['id']}",
            payload={
                "draft_id": draft["id"],
                "content_sha256": draft.get("content_sha256"),
                "local_sha256": content_sha,
                "to": case.authority_email,
                "subject": subject,
                "text": text,
                "estimate_id": str(est.id),
                "inbox_address": inbox.get("address"),
                "attachment": "notchcount-report.pdf",
            },
        )
    )
    await db.commit()
    return await _case_out(db, settings, case, survey)


@router.post("/cases/{case_id}/drafts/{draft_id}/approve", response_model=CaseOut)
async def approve_and_send(
    case_id: uuid.UUID, draft_id: str, user: UserDep, db: DbDep, settings: SettingsDep
) -> CaseOut:
    case, survey, _ = await _case_for(db, user, case_id, Role.ADMIN)
    draft_event = (
        await db.execute(
            select(CaseEvent).where(
                CaseEvent.case_id == case.id, CaseEvent.external_id == f"draft:{draft_id}"
            )
        )
    ).scalar_one_or_none()
    if draft_event is None or case.agentboxd_inbox_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That draft is not in this case.")
    already = (
        await db.execute(
            select(CaseEvent).where(CaseEvent.case_id == case.id, CaseEvent.external_id == f"sent:{draft_id}")
        )
    ).scalar_one_or_none()
    if already is not None:
        return await _case_out(db, settings, case, survey)
    db.add(
        CaseEvent(
            case_id=case.id, kind=CaseEventKind.APPROVED, actor_id=user.id, payload={"draft_id": draft_id}
        )
    )
    await db.flush()
    key = settings.agentboxd_send_key.get_secret_value() if settings.agentboxd_send_key else None
    try:
        async with AgentboxdClient(settings.agentboxd_base_url, key, TRANSPORT) as ab:
            sent = await ab.send_draft(
                case.agentboxd_inbox_id, draft_id, draft_event.payload.get("content_sha256")
            )
    except FilingError as exc:
        db.add(
            CaseEvent(
                case_id=case.id, kind=CaseEventKind.ERROR, actor_id=user.id, payload={"error": str(exc)}
            )
        )
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    message = sent.get("message") or {}
    db.add(
        CaseEvent(
            case_id=case.id,
            kind=CaseEventKind.SENT,
            actor_id=user.id,
            external_id=f"sent:{draft_id}",
            payload={
                "draft_id": draft_id,
                "message_id": message.get("id"),
                "status": message.get("status"),
                "to": draft_event.payload.get("to"),
            },
        )
    )
    case.status = "sent"
    await db.commit()
    return await _case_out(db, settings, case, survey)


@webhooks.post("/webhooks/agentboxd", status_code=status.HTTP_204_NO_CONTENT)
async def agentboxd_webhook(request: Request, db: DbDep, settings: SettingsDep) -> None:
    """Replies are stored as untrusted text for people to read. Nothing parses or acts on them."""
    if settings.agentboxd_webhook_secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook secret not configured.")
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Payload too large.")
    if not verify_webhook(
        settings.agentboxd_webhook_secret.get_secret_value(),
        request.headers.get("x-mailroom-timestamp"),
        request.headers.get("x-mailroom-signature"),
        raw,
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature.")
    try:
        event = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Body is not JSON.") from exc
    if event.get("type") != "message.received":
        return
    data = event.get("data") or {}
    inbox_id = str((data.get("inbox") or {}).get("id") or data.get("inbox_id") or "")
    case = (await db.execute(select(Case).where(Case.agentboxd_inbox_id == inbox_id))).scalar_one_or_none()
    if case is None:
        return
    message = data.get("message") or {}
    labels = [str(x) for x in (message.get("labels") or data.get("labels") or [])][:20]
    held = should_hold(labels)
    external = f"msg:{message.get('id') or event.get('id')}"
    exists = (
        await db.execute(select(CaseEvent.id).where(CaseEvent.external_id == external))
    ).scalar_one_or_none()
    if exists is not None:
        return
    db.add(
        CaseEvent(
            case_id=case.id,
            kind=CaseEventKind.HELD if held else CaseEventKind.REPLY,
            external_id=external,
            payload={
                "untrusted_text": str(message.get("extracted_text") or "")[:20000],
                "from": str(message.get("from") or data.get("from") or "")[:320],
                "subject": str(message.get("subject") or data.get("subject") or "")[:500],
                "labels": labels,
                "thread_id": data.get("thread_id"),
                "received_at": event.get("created_at") or datetime.now(UTC).isoformat(),
            },
        )
    )
    if not held:
        case.status = "replied"
    await db.commit()
