import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.track import ModuleLevel
from app.models.user import Role


# --- Auth ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- User ---
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.STUDENT


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: Role
    is_active: bool


# --- Track / Module / Lesson ---
class LessonCreate(BaseModel):
    title: str
    content: str = ""
    position: int


class LessonUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    position: int | None = None
    is_active: bool | None = None


class LessonOut(LessonCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool


class ModuleCreate(BaseModel):
    title: str
    level: ModuleLevel = ModuleLevel.BEGINNER
    position: int


class ModuleUpdate(BaseModel):
    title: str | None = None
    level: ModuleLevel | None = None
    position: int | None = None
    is_active: bool | None = None


class ModuleOut(ModuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    lessons: list[LessonOut] = []


class TrackCreate(BaseModel):
    title: str
    description: str = ""
    competency: str = ""


class TrackUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    competency: str | None = None
    published: bool | None = None
    is_active: bool | None = None


class TrackOut(TrackCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    published: bool
    is_active: bool
    modules: list[ModuleOut] = []


# --- Cohort ---
class ModuleProfessorIn(BaseModel):
    module_id: uuid.UUID
    professor_id: uuid.UUID


class ModuleProfessorOut(ModuleProfessorIn):
    module_title: str
    professor_name: str


class CohortCreate(BaseModel):
    name: str
    track_id: uuid.UUID
    module_professors: list[ModuleProfessorIn]


class CohortUpdate(BaseModel):
    name: str | None = None
    module_professors: list[ModuleProfessorIn] | None = None


class CohortOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    track_id: uuid.UUID


class CohortListOut(CohortOut):
    track_title: str
    enrollment_count: int = 0
    module_professors: list[ModuleProfessorOut] = []


class CohortDetailOut(CohortListOut):
    pass


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    student_email: str
    enrolled_at: datetime


class CohortProgressOut(BaseModel):
    completed_lesson_ids: list[uuid.UUID]
    current_lesson_id: uuid.UUID | None = None


# --- Lesson completion ---
class LessonCompletionIn(BaseModel):
    lesson_id: uuid.UUID
    transcript: str = ""  # professor's audio text (or already transcribed)


class TranscriptionOut(BaseModel):
    transcript: str


# --- Conversation ---
class MessageIn(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author: str
    content: str
    created_at: datetime


class AgentResponse(BaseModel):
    conversation_id: uuid.UUID
    response: str
