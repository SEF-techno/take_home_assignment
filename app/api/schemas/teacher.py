from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TeacherCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(pattern=r"^[0-9]{8,15}$")
    cohort_id: UUID

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class TeacherRead(TeacherCreate):
    id: UUID
