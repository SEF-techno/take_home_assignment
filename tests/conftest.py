"""Integration fixtures: each test owns a migrated PostgreSQL database."""
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import db_settings
from app.db.session import get_session
from app.main import app


async def admin_connection():
    return await asyncpg.connect(
        host=db_settings.POSTGRES_SERVER,
        port=db_settings.POSTGRES_PORT,
        user=db_settings.POSTGRES_USERNAME,
        password=db_settings.POSTGRES_PASSWORD,
        database="postgres",
    )


@pytest.fixture
def database():
    name = f"assignment_test_{uuid4().hex}"

    async def create():
        connection = await admin_connection()
        try:
            await connection.execute(f'CREATE DATABASE "{name}"')
        finally:
            await connection.close()

    asyncio.run(create())
    env = {**os.environ, "POSTGRES_DB": name}
    try:
        subprocess.run(
            [str(Path(sys.executable).with_name("alembic")), "upgrade", "head"],
            env=env, check=True, capture_output=True, text=True,
        )
        url = db_settings.POSTGRES_URL.rsplit("/", 1)[0] + "/" + name
        engine = create_async_engine(url, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def test_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_session] = test_session
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()

        async def drop():
            connection = await admin_connection()
            try:
                await connection.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = $1 AND pid <> pg_backend_pid()", name
                )
                await connection.execute(f'DROP DATABASE IF EXISTS "{name}"')
            finally:
                await connection.close()

        asyncio.run(drop())


@pytest.fixture
def outbound_message(database):
    client, sessions = database

    async def create():
        from app.db.models import Campaign, CampaignStatus, Cohort, Message, MessageDirection, Teacher

        async with sessions() as session:
            cohort = Cohort(name="Test cohort", region="Test region")
            campaign = Campaign(name="Test campaign", status=CampaignStatus.PLANNED)
            session.add_all([cohort, campaign])
            await session.flush()
            teacher = Teacher(name="Test teacher", phone="919876500001", cohort_id=cohort.id)
            session.add(teacher)
            await session.flush()
            message = Message(
                provider="fake_provider", provider_message_id="test_message_001",
                content="Hello", direction=MessageDirection.OUTBOUND,
                campaign_id=campaign.id, teacher_id=teacher.id,
            )
            session.add(message)
            await session.commit()
            return message.id

    return client, sessions, asyncio.run(create())
