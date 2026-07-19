import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.conversation import _enum_values


class StudentLessonProgressStatus(str, enum.Enum):
    DISPARADA = "disparada"
    ATIVA = "ativa"
    CONCLUIDA = "concluida"
    ENCERRADA_POR_AVANCO = "encerrada_por_avanco"


class StudentLessonProgress(Base):
    """Per-student lesson progression within a cohort."""

    __tablename__ = "student_lesson_progress"
    __table_args__ = (
        UniqueConstraint(
            "cohort_id", "student_id", "lesson_id", name="uq_student_lesson_progress"
        ),
    )

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[StudentLessonProgressStatus] = mapped_column(
        Enum(
            StudentLessonProgressStatus,
            values_callable=_enum_values,
            native_enum=False,
            length=30,
        ),
        default=StudentLessonProgressStatus.DISPARADA,
        server_default="disparada",
        nullable=False,
    )
    disparada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    concluded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    encerrada_por_avanco_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
