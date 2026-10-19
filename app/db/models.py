"""
Database models and enums for the application.

The models in this module cover users, campaigns, cohorts, teachers,
messages, message events, and audit events.
"""


from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


# Enums
class MessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class CampaignStatus(str, Enum):
    PLANNED = "Planned"
    Ongoing = "Ongoing"
    FINISHED = "Finished"
    ABORTED = "Aborted"

class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class AuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


# Base models
class UserBase(SQLModel):
    name: str

    email: EmailStr
    email_verified: bool = Field(default=False)
    is_active: bool = Field(default=False)
    password_hash: str


# Models
class User(UserBase, table=True):
    __tablename__ = "user"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    created_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

class Cohort(SQLModel, table=True):
    __tablename__ = "cohort"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    name: str

    teachers: list["Teacher"] = Relationship(
        back_populates= "cohort",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    region: str

class Campaign(SQLModel, table=True):
    __tablename__ = "campaign"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    name: str
    description: str | None = Field(default=None)

    status: CampaignStatus
    status_remark: str | None = Field(default=None)

    created_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

    messages: list["Message"] = Relationship(
        back_populates="campaign",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

class Teacher(SQLModel, table = True):
    __tablename__ = "teacher"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    name: str
    phone: str = Field(unique=True)

    cohort_id: UUID = Field(foreign_key="cohort.id")

    cohort: Cohort = Relationship(
        back_populates="teachers",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    messages: list["Message"] = Relationship(
        back_populates="teacher",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

class Message(SQLModel, table=True):
    __tablename__ = "message"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    provider: str
    provider_message_id: str

    content: str
    direction: MessageDirection

    created_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

    status_updated_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

    timeline: list["MessageEvent"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "order_by": "MessageEvent.event_timestamp",
        },
    )

    campaign_id: UUID | None = Field(
        default=None,
        foreign_key="campaign.id",
    )

    campaign: Campaign | None = Relationship(
        back_populates="messages",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    teacher_id: UUID = Field(foreign_key="teacher.id")
    teacher: Teacher = Relationship(
        back_populates="messages",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    @property
    def current_status(self):
        return self.timeline[-1].status if len(self.timeline) > 0 else None

class MessageEvent(SQLModel, table=True):
    __tablename__ = "message_event"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

    status: MessageStatus

    provider: str
    provider_event_id: str = Field(unique=True)
    event_timestamp: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            nullable=False,
        )
    )

    received_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )

    raw_payload: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False)
    )

    message_id:UUID = Field(
        foreign_key="message.id"
    )

    message: Message = Relationship(
        back_populates="timeline",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

class AutidEvent(SQLModel, table=True):
    __tablename__ = "audit_event"

    id: UUID = Field(
        sa_column=Column(postgresql.UUID, default=uuid4, primary_key=True),
    )

    entity_type: str
    entity_id: UUID

    action: AuditAction
    actor_id: UUID = Field(foreign_key="user.id", nullable=True)


    changes: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    event_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    created_at: datetime = Field(
        sa_column=Column(
            postgresql.TIMESTAMP,
            default=datetime.now,
        )
    )






