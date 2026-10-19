from fastapi import APIRouter, status

from app.api.api_tag import APITag
from app.api.dependencies import TeacherServiceDep, UserAuthDep
from app.api.schemas.teacher import TeacherCreate, TeacherRead

router = APIRouter(prefix="/teacher", tags=[APITag.TEACHER])


@router.post("/", response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
async def create_teacher(data: TeacherCreate, user: UserAuthDep, service: TeacherServiceDep):
    return await service.create_teacher(data, user)
