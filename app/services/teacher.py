from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.teacher import TeacherCreate
from app.db.models import AuditAction, AutidEvent, Cohort, Teacher, User
from app.services.base import BaseService


class TeacherService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__(Teacher, session)

    async def create_teacher(self, data: TeacherCreate, actor: User) -> Teacher:
        if await self.session.get(Cohort, data.cohort_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cohort does not exist")

        existing = await self.session.scalar(
            select(Teacher.id).where(Teacher.phone == data.phone)
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Phone already belongs to a teacher")

        teacher = Teacher(**data.model_dump())
        try:
            self.session.add(teacher)
            await self.session.flush()
            self.session.add(AutidEvent(
                entity_type="teacher",
                entity_id=teacher.id,
                action=AuditAction.CREATED,
                actor_id=actor.id,
                changes={
                    "name": {"from": None, "to": teacher.name},
                    "phone": {"from": None, "to": teacher.phone},
                    "cohort_id": {"from": None, "to": str(teacher.cohort_id)},
                },
            ))
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Teacher could not be created")
        await self.session.refresh(teacher)
        return teacher
