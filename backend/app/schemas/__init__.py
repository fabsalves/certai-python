import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.email import normalize_email
from app.core.phone import normalize_br_phone
from app.models.track import ModuleLevel
from app.models.user import Role


def _require_non_empty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Não pode ficar vazio")
    return value


def _optional_non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    return _require_non_empty(value)


NameStr = Annotated[str, AfterValidator(_require_non_empty), Field(max_length=255)]
OptionalNameStr = Annotated[str | None, AfterValidator(_optional_non_empty)]
def _optional_whatsapp(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = normalize_br_phone(value)
    if normalized is None:
        raise ValueError("WhatsApp inválido")
    return normalized


def _required_whatsapp(value: str) -> str:
    if not str(value).strip():
        raise ValueError("WhatsApp é obrigatório")
    normalized = normalize_br_phone(value)
    if normalized is None:
        raise ValueError("WhatsApp inválido")
    return normalized


NormalizedEmailStr = Annotated[EmailStr, AfterValidator(normalize_email)]
OptionalWhatsappStr = Annotated[str | None, AfterValidator(_optional_whatsapp)]
RequiredWhatsappStr = Annotated[str, AfterValidator(_required_whatsapp)]


# --- Auth ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- User ---
class UserBase(BaseModel):
    email: NormalizedEmailStr
    name: NameStr


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.STUDENT
    whatsapp: OptionalWhatsappStr = None

    @model_validator(mode="after")
    def require_whatsapp_for_students(self) -> "UserCreate":
        if self.role == Role.STUDENT and not self.whatsapp:
            raise ValueError("WhatsApp é obrigatório para alunos")
        return self


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: Role
    is_active: bool
    whatsapp: str | None = None


class StudentBulkItem(BaseModel):
    name: NameStr
    email: NormalizedEmailStr
    whatsapp: RequiredWhatsappStr


class StudentBulkCreate(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    students: list[StudentBulkItem] = Field(min_length=1)


class StudentBulkSkipped(BaseModel):
    email: str
    reason: str


class StudentBulkOut(BaseModel):
    created: list[UserOut]
    reused_ids: list[uuid.UUID]
    skipped: list[StudentBulkSkipped]


# --- Track / Module / Lesson ---
class LessonCreate(BaseModel):
    title: NameStr
    content: str = ""
    position: int


class LessonUpdate(BaseModel):
    title: OptionalNameStr = None
    content: str | None = None
    position: int | None = None
    is_active: bool | None = None


class LessonOut(LessonCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool


class ModuleCreate(BaseModel):
    title: NameStr
    level: ModuleLevel = ModuleLevel.BEGINNER
    position: int


class ModuleUpdate(BaseModel):
    title: OptionalNameStr = None
    level: ModuleLevel | None = None
    position: int | None = None
    is_active: bool | None = None


class ModuleOut(ModuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    lessons: list[LessonOut] = []


class TrackCreate(BaseModel):
    title: NameStr
    description: str = ""
    competency: str = ""


class TrackUpdate(BaseModel):
    title: OptionalNameStr = None
    description: str | None = None
    competency: str | None = None
    published: bool | None = None
    is_active: bool | None = None


class TrackOut(TrackCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    published: bool
    is_active: bool
    material_filename: str | None = None
    material_content_type: str | None = None
    material_ingestion_status: str | None = None
    modules: list[ModuleOut] = []


# --- Cohort ---
class ModuleProfessorIn(BaseModel):
    module_id: uuid.UUID
    professor_id: uuid.UUID


class ModuleProfessorOut(ModuleProfessorIn):
    module_title: str
    professor_name: str


class CohortCreate(BaseModel):
    name: NameStr
    track_id: uuid.UUID
    module_professors: list[ModuleProfessorIn]


class CohortUpdate(BaseModel):
    name: OptionalNameStr = None
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


class EnrollmentBulkCreate(BaseModel):
    student_ids: list[uuid.UUID]


class EnrollmentBulkOut(BaseModel):
    enrolled_count: int
    skipped_count: int = 0


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    student_email: str
    student_whatsapp: str | None = None
    enrolled_at: datetime


class CohortProgressOut(BaseModel):
    completed_lesson_ids: list[uuid.UUID]
    current_lesson_id: uuid.UUID | None = None


class CohortLessonNoteOut(BaseModel):
    lesson_id: uuid.UUID
    attachment_filename: str | None = None
    has_attachment: bool = False
    has_audio: bool = False
    ingestion_status: str = "done"


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


# --- Playground (admin debug) ---
class PlaygroundTrackMaterialOut(BaseModel):
    filename: str | None = None
    ingestion_status: str | None = None
    guide: str = ""
    in_ai_bundle: bool = False


class PlaygroundLessonNoteContextOut(BaseModel):
    lesson_id: uuid.UUID
    lesson_title: str
    ingestion_status: str | None = None
    summary: str = ""
    unclear_points: str = ""
    knowledge_base: str = ""
    has_attachment: bool = False
    attachment_filename: str | None = None
    in_ai_bundle: bool = False


class PlaygroundContextOut(BaseModel):
    scope: str
    current_position: dict | None = None
    track_map: list[dict]
    unlocked_content: list[dict]
    cohort_notes_in_bundle: list[dict]
    track_guide_in_bundle: str = ""
    system_blocks: str
    track_material: PlaygroundTrackMaterialOut
    lesson_notes: list[PlaygroundLessonNoteContextOut] = []
