import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.api import dependencies
from app.db.models import AuditAction, AutidEvent, Cohort, Teacher, User
from app.utils import generate_access_token


def test_create_teacher_requires_auth_and_valid_cohort(database, monkeypatch):
    client, sessions = database

    async def setup():
        async with sessions() as session:
            cohort = Cohort(name="Teacher test", region="Test")
            user = User(name="Creator", email="creator@example.com", password_hash="unused")
            session.add_all([cohort, user])
            await session.commit()
            return cohort.id, user.id

    cohort_id, user_id = asyncio.run(setup())
    body = {"name": "  Aisha  ", "phone": "919876500002", "cohort_id": str(cohort_id)}
    assert client.post("/teacher/", json=body).status_code == 401

    async def never_blacklisted(_jti):
        return False

    monkeypatch.setattr(dependencies, "is_jti_blacklisted", never_blacklisted)
    token = generate_access_token({"user": {"id": str(user_id)}})
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/teacher/", json={**body, "cohort_id": str(uuid4())}, headers=headers).status_code == 404
    created = client.post("/teacher/", json=body, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Aisha"
    assert created.json()["cohort_id"] == str(cohort_id)
    assert client.post("/teacher/", json=body, headers=headers).status_code == 409

    async def persisted():
        async with sessions() as session:
            teachers = (await session.scalars(select(Teacher))).all()
            audits = (await session.scalars(select(AutidEvent))).all()
            return teachers, audits

    teachers, audits = asyncio.run(persisted())
    assert len(teachers) == 1
    assert len(audits) == 1
    assert audits[0].action == AuditAction.CREATED
    assert audits[0].actor_id == user_id
