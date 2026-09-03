import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.email import normalize_email
from app.core.phone import normalize_br_phone
from app.models.student_progress import StudentLessonProgressStatus
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
    organization_id: uuid.UUID | None = None


class UserCreatedOut(UserOut):
    """Create response. initial_password only for staff (platform login)."""

    initial_password: str | None = None


class UserUpdate(BaseModel):
    name: NameStr
    email: NormalizedEmailStr
    whatsapp: OptionalWhatsappStr = None
    role: Role | None = None
    is_active: bool | None = None


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=10, max_length=128)


class StudentBulkItem(BaseModel):
    name: NameStr
    email: NormalizedEmailStr
    whatsapp: RequiredWhatsappStr


class StudentBulkCreate(BaseModel):
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
    content_source_filename: str | None = None
    content_source_content_type: str | None = None
    content_source_kind: str | None = None  # audio | document


class ModuleCreate(BaseModel):
    title: NameStr
    description: str = ""
    level: ModuleLevel = ModuleLevel.BEGINNER
    position: int


class ModuleUpdate(BaseModel):
    title: OptionalNameStr = None
    description: str | None = None
    level: ModuleLevel | None = None
    position: int | None = None
    is_active: bool | None = None


class ModuleOut(ModuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    description_source_filename: str | None = None
    description_source_content_type: str | None = None
    description_source_kind: str | None = None
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
    description_source_filename: str | None = None
    description_source_content_type: str | None = None
    description_source_kind: str | None = None
    modules: list[ModuleOut] = []


# --- Cohort ---
class ModuleProfessorIn(BaseModel):
    """One teaching class. student_ids is only meaningful when the module has
    more than one professor; with a single one the whole cohort is the class."""

    module_id: uuid.UUID
    professor_id: uuid.UUID
    student_ids: list[uuid.UUID] = []


class ModuleProfessorOut(ModuleProfessorIn):
    id: uuid.UUID
    module_title: str
    professor_name: str


class CohortCreate(BaseModel):
    name: NameStr
    track_id: uuid.UUID
    module_professors: list[ModuleProfessorIn]
    # A test cohort, whose progression the admin can rewind. Only settable here:
    # CohortUpdate has no such field, which is what makes the mark immutable.
    is_sandbox: bool = False


class CohortUpdate(BaseModel):
    name: OptionalNameStr = None
    module_professors: list[ModuleProfessorIn] | None = None
    # `is_sandbox` is deliberately absent -- see Cohort.is_sandbox.


class CohortOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    track_id: uuid.UUID
    is_sandbox: bool = False


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


class UnassignedStudentOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    student_email: str


class ClaimClassStudentIn(BaseModel):
    student_id: uuid.UUID


class LessonClassStatusOut(BaseModel):
    """How one class stands on one lesson."""

    module_professor_id: uuid.UUID
    professor_id: uuid.UUID
    professor_name: str
    closed: bool
    closed_at: datetime | None = None
    # Standing coverage of this lesson for this class. `pending` non-empty means
    # part of the planned content was not taught -- delta as operational data.
    covered: str = ""
    pending: str = ""
    extent: str = ""  # "" when nothing was reported | full | partial


class LessonClassesOut(BaseModel):
    lesson_id: uuid.UUID
    classes: list[LessonClassStatusOut] = []
    # Some class closed it, another has not -- and a later lesson already moved on.
    delayed: bool = False


class CohortProgressOut(BaseModel):
    # Lessons every class of their module has closed.
    completed_lesson_ids: list[uuid.UUID]
    # Closed by at least one class, still pending for another.
    partial_lesson_ids: list[uuid.UUID] = []
    # Next lesson for the requester (their own class, when a professor).
    current_lesson_id: uuid.UUID | None = None
    lesson_classes: list[LessonClassesOut] = []


class StudentLessonProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cohort_id: uuid.UUID
    student_id: uuid.UUID
    lesson_id: uuid.UUID
    status: StudentLessonProgressStatus
    disparada_at: datetime
    activated_at: datetime | None = None
    concluded_at: datetime | None = None
    encerrada_por_avanco_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CohortLessonNoteOut(BaseModel):
    lesson_id: uuid.UUID
    module_professor_id: uuid.UUID
    professor_id: uuid.UUID
    professor_name: str
    attachment_filename: str | None = None
    has_attachment: bool = False
    has_audio: bool = False
    audio_filename: str | None = None
    audio_source: str | None = None  # "recording" | "file"
    ingestion_status: str = "done"


# --- Layered student assessments (read) ---
class StudentAssessmentOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    scope: str  # lesson | module | track
    lesson_id: uuid.UUID | None = None
    module_id: uuid.UUID | None = None
    track_id: uuid.UUID | None = None
    scope_title: str = ""
    level: str | None = None  # null = insufficient evidence
    assessment: str = ""
    gaps: str = ""
    created_at: datetime


class PendingAssessmentStudentOut(BaseModel):
    student_id: uuid.UUID
    student_name: str


class LessonAssessmentsOut(BaseModel):
    lesson_id: uuid.UUID
    assessments: list[StudentAssessmentOut] = []
    pending: list[PendingAssessmentStudentOut] = []


class StudentAssessmentsOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    assessments: list[StudentAssessmentOut] = []


class LessonMicroScoreOut(BaseModel):
    id: uuid.UUID
    competency: str = ""
    level: str
    evidence: str = ""
    created_at: datetime


class LessonMicroScoresOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    lesson_id: uuid.UUID
    lesson_title: str
    scores: list[LessonMicroScoreOut] = []


class CohortTrackLevelOut(BaseModel):
    student_id: uuid.UUID
    level: str | None = None  # null = insufficient evidence, or no assessment
    has_assessment: bool


class CohortTrackLevelsOut(BaseModel):
    students: list[CohortTrackLevelOut] = []


class SandboxRewindOut(BaseModel):
    """What a rewind removed, so the UI can report it back."""

    action: Literal["undo_last_closure", "reset_progress"]
    lesson_title: str = ""      # undo only: the closure that was undone
    professor_name: str = ""    # undo only
    removed: dict[str, int] = {}


# --- Lesson coverage (planned vs. taught) ---
CoverageKindLiteral = Literal["planned", "carryover", "advance"]
CoverageExtentLiteral = Literal["full", "partial"]

# Coverage prose is written by the LLM or edited by the professor; cap it so a
# runaway generation or a pasted document cannot bloat the context bundle.
COVERAGE_TEXT_MAX = 2000


class CoverageSegmentIn(BaseModel):
    """One lesson touched by a teaching session, as confirmed by the professor."""

    lesson_id: uuid.UUID
    kind: CoverageKindLiteral
    extent: CoverageExtentLiteral
    covered: str = Field(default="", max_length=COVERAGE_TEXT_MAX)
    pending: str = Field(default="", max_length=COVERAGE_TEXT_MAX)
    source: Literal["ai", "professor"] = "ai"

    @model_validator(mode="after")
    def _pending_requires_partial(self):
        """A fully covered lesson owes nothing -- keep the two fields coherent."""
        if self.extent == "full" and self.pending.strip():
            self.pending = ""
        return self


class CoverageSegmentOut(CoverageSegmentIn):
    lesson_title: str = ""


class CoverageCandidateOut(BaseModel):
    """A lesson the session may legitimately have touched."""

    lesson_id: uuid.UUID
    lesson_title: str = ""
    is_anchor: bool = False
    # What this lesson already owed before this session.
    standing_pending: str = ""


class CoverageNoticeOut(BaseModel):
    """Content the report describes that this class cannot record.

    A professor does finish their last lesson and carry on into the next module.
    When that module is another professor's, the content was taught but there is
    no honest place to record it here -- so it is surfaced instead of dropped.
    """

    lesson_title: str = ""
    professor_name: str = ""
    covered: str = Field(default="", max_length=COVERAGE_TEXT_MAX)


class CoverageProposalOut(BaseModel):
    """What the AI derived from the report, for the professor to confirm."""

    anchor_lesson_id: uuid.UUID
    segments: list[CoverageSegmentOut] = []
    # The window the professor may add a lesson from, when the AI missed one.
    candidates: list[CoverageCandidateOut] = []
    # Described in the report, taught for real, and not recordable by this class.
    unrecordable: list[CoverageNoticeOut] = []
    # False when the AI call failed: the client falls back to the anchor-only
    # default and the professor can still close the lesson.
    from_ai: bool = True


class LessonCoverageOut(BaseModel):
    """Standing coverage of a lesson for one teaching class (read)."""

    lesson_id: uuid.UUID
    kind: CoverageKindLiteral
    extent: CoverageExtentLiteral
    covered: str = ""
    pending: str = ""
    source: str = "ai"
    created_at: datetime


# --- Lesson completion ---
class LessonCompletionIn(BaseModel):
    lesson_id: uuid.UUID
    transcript: str = ""  # professor's audio text (or already transcribed)


class LessonCompletionOut(BaseModel):
    """Result of closing a lesson.

    `coverage_ignored` is normally empty. It fills when a segment the professor
    confirmed could not be recorded -- the candidate window shrank between the
    proposal and the submit. Reported rather than dropped in silence: losing what
    a human declared is the failure mode this package exists to remove.
    """

    status: str
    ingestion_status: str
    coverage_ignored: list[str] = []


class TranscriptionOut(BaseModel):
    transcript: str


class ImportTextOut(BaseModel):
    """Text extracted/transcribed for the lesson content field (+ source file meta)."""

    text: str = ""
    content_source_filename: str | None = None
    content_source_content_type: str | None = None
    content_source_kind: str | None = None


# --- Conversation ---
class MessageIn(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author: str
    content: str
    created_at: datetime
    source: str | None = None


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
    # Only when the session diverged from the plan; empty on the happy path.
    taught_scope: list[dict] = []
    cohort_notes_in_bundle: list[dict]
    track_guide_in_bundle: str = ""
    system_blocks: str
    track_material: PlaygroundTrackMaterialOut
    lesson_notes: list[PlaygroundLessonNoteContextOut] = []


class PlaygroundLessonFocusOut(BaseModel):
    lesson_id: uuid.UUID
    lesson_title: str


class PlaygroundMicroScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lesson_id: uuid.UUID | None = None
    lesson_title: str = ""
    competency: str = ""
    level: str
    evidence: str = ""
    created_at: datetime


class PlaygroundScoresOut(BaseModel):
    track_competency: str = ""
    lesson_focus: PlaygroundLessonFocusOut
    scores_in_lesson: list[PlaygroundMicroScoreOut] = []
    scores_other_lessons: list[PlaygroundMicroScoreOut] = []


# --- Custos de IA -----------------------------------------------------------
# Valores em USD. A conversão para BRL é exibição (settings.USD_BRL_RATE).
# `unpriced_events > 0` significa total INCOMPLETO — a tela deve avisar.


class KindBreakdownOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cost_kind: str
    label: str
    provider: str
    total_tokens: float
    cost_usd: float
    unpriced_events: int = 0
    voice_minutes_est: float = 0


class LessonCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lesson_id: uuid.UUID | None = None
    lesson_title: str
    module_title: str = ""
    voice_minutes_est: float = 0
    voice_cost_usd: float = 0
    other_cost_usd: float = 0
    cost_usd: float = 0
    unpriced_events: int = 0


class StudentCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: uuid.UUID | None = None
    student_name: str
    lesson_count: int = 0
    voice_minutes_est: float = 0
    cost_usd: float = 0
    cost_per_lesson_usd: float = 0
    unpriced_events: int = 0


class CohortCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cohort_id: uuid.UUID
    cohort_title: str
    track_id: uuid.UUID | None = None
    track_title: str = ""
    student_count: int = 0
    lesson_count: int = 0
    student_lesson_count: int = 0
    voice_minutes_est: float = 0
    cost_usd: float = 0
    cost_per_student_usd: float = 0
    # Custo de UMA avaliação por aluno: total / pares (aluno, aula) medidos.
    cost_per_student_lesson_usd: float = 0
    unpriced_events: int = 0


class CohortsCostOut(BaseModel):
    cohorts: list[CohortCostOut] = []
    total_cost_usd: float = 0
    # Ingestão de material de trilha: gasto real sem turma para atribuir.
    unattributed_cost_usd: float = 0
    unpriced_events: int = 0
    models: list[str] = []
    usd_brl_rate: float
    period_from: datetime
    period_to: datetime


class CohortCostDetailOut(BaseModel):
    cohort_id: uuid.UUID
    cohort_title: str
    track_title: str = ""
    voice_minutes_est: float = 0
    cost_usd: float = 0
    unpriced_events: int = 0
    by_kind: list[KindBreakdownOut] = []
    students: list[StudentCostOut] = []
    models: list[str] = []
    usd_brl_rate: float
    period_from: datetime
    period_to: datetime


class StudentCostDetailOut(BaseModel):
    cohort_id: uuid.UUID
    cohort_title: str
    student_id: uuid.UUID
    student_name: str
    voice_minutes_est: float = 0
    cost_usd: float = 0
    unpriced_events: int = 0
    by_kind: list[KindBreakdownOut] = []
    lessons: list[LessonCostOut] = []
    models: list[str] = []
    usd_brl_rate: float
    period_from: datetime
    period_to: datetime


# --- Organizations ---
class OrgCreate(BaseModel):
    name: NameStr
    slug: OptionalNameStr = None


class OrgUpdate(BaseModel):
    name: NameStr


class OrgListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    user_count: int = 0
    created_at: datetime


class ModelOptionOut(BaseModel):
    id: str
    label: str
    provider: str
    category: str
    group: str
    description: str
    context: str | None = None
    badge: str | None = None


class SettingsCatalogOut(BaseModel):
    version: str
    chat_models: list[ModelOptionOut]
    openai_realtime_models: list[ModelOptionOut]
    openai_realtime_voices: list[ModelOptionOut]
    groq_transcribe_models: list[ModelOptionOut]
    defaults: dict[str, str]


class OrgSettingsOut(BaseModel):
    organization_slug: str = ""
    webhook_base_url: str = ""
    engine_model: str
    humanizer_model: str
    evaluator_model: str
    groq_transcribe_model: str
    openai_realtime_model: str
    openai_realtime_voice: str
    cinndi_api_url: str
    cinndi_sender_phone: str
    whatsapp_invite_template: str
    whatsapp_invite_voice_template: str
    whatsapp_invite_use_voice_template: bool
    whatsapp_template_lang: str
    assistant_name: str
    configured: dict[str, bool]
    available: dict[str, bool] = Field(default_factory=dict)
    masked_secrets: dict[str, str]


class OrgSettingsUpdate(BaseModel):
    engine_model: str | None = None
    humanizer_model: str | None = None
    evaluator_model: str | None = None
    groq_transcribe_model: str | None = None
    openai_realtime_model: str | None = None
    openai_realtime_voice: str | None = None
    cinndi_api_url: str | None = None
    cinndi_sender_phone: str | None = None
    whatsapp_invite_template: str | None = None
    whatsapp_invite_voice_template: str | None = None
    whatsapp_invite_use_voice_template: bool | None = None
    whatsapp_template_lang: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    cinndi_api_key: str | None = None
    cinndi_webhook_token: str | None = None
    clear_secrets: list[str] = Field(default_factory=list)


class OrgDetailOut(OrgListItem):
    settings: OrgSettingsOut


class AdminUserOut(UserOut):
    organization_name: str | None = None


class CredentialTestRequest(BaseModel):
    field: Literal["openai_api_key", "groq_api_key"]
    value: str | None = Field(default=None, max_length=500)


class CredentialTestResponse(BaseModel):
    ok: bool = True
    message: str
