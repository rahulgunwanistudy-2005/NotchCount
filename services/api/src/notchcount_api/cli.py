"""Admin command line: create the first team and admin, or issue a new sign-in link.

uv run nc-admin bootstrap --team "Gali 4 walkers" --city "Delhi" --admin "Asha"
uv run nc-admin invite --user <user-id>
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select

from notchcount_api.auth.invites import create_invite
from notchcount_api.config import get_settings
from notchcount_api.db.models import Role, Team, TeamMember, User
from notchcount_api.db.session import get_sessionmaker


async def bootstrap(team_name: str, city: str, admin_name: str) -> None:
    settings = get_settings()
    async with get_sessionmaker()() as db:
        team = Team(name=team_name, city=city)
        user = User(auth_subject=f"invite:{uuid.uuid4()}", display_name=admin_name)
        db.add_all([team, user])
        await db.flush()
        db.add(TeamMember(team_id=team.id, user_id=user.id, role=Role.ADMIN))
        code = await create_invite(db, user.id)
        await db.commit()
    print(f"team {team.id}")
    print(f"admin {user.id}")
    print(f"sign-in link (one use, 7 days): {settings.public_base_url}/join#{code}")


async def invite(user_id: uuid.UUID) -> None:
    settings = get_settings()
    async with get_sessionmaker()() as db:
        if (await db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none() is None:
            raise SystemExit(f"no user {user_id}")
        code = await create_invite(db, user_id)
        await db.commit()
    print(f"sign-in link (one use, 7 days): {settings.public_base_url}/join#{code}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="nc-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap")
    b.add_argument("--team", required=True)
    b.add_argument("--city", required=True)
    b.add_argument("--admin", required=True)
    i = sub.add_parser("invite")
    i.add_argument("--user", required=True, type=uuid.UUID)
    args = parser.parse_args()
    if args.cmd == "bootstrap":
        asyncio.run(bootstrap(args.team, args.city, args.admin))
    else:
        asyncio.run(invite(args.user))


if __name__ == "__main__":
    main()
