import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Cohort(Base):
    """Group of students going through a track. Progression is per cohort."""

    __tablename__ = "cohorts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="RESTRICT"), index=True
    )

    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="cohort", cascade="all, delete-orphan"
    )
    progress: Mapped[list["CohortProgress"]] = relationship(
        back_populates="cohort", cascade="all, delete-orphan"
    )
    module_professors: Mapped[list["CohortModuleProfessor"]] = relationship(
        back_populates="cohort", cascade="all, delete-orphan"
    )


class CohortModuleProfessor(Base):
    """Professor assigned to a module within a cohort's track."""

    __tablename__ = "cohort_module_professors"
    __table_args__ = (
        UniqueConstraint("cohort_id", "module_id", name="uq_cohort_module_professor"),
    )

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="RESTRICT"), index=True
    )
    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    cohort: Mapped[Cohort] = relationship(back_populates="module_professors")


class Enrollment(Base):
    """Student <> cohort link."""

    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("cohort_id", "student_id", name="uq_enrollment"),)

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    cohort: Mapped[Cohort] = relationship(back_populates="enrollments")


class CohortProgress(Base):
    """Lessons the cohort has studied. Written when the professor signals completion.

    The existence of a row here is what unlocks the lesson context for students.
    A future lesson has no row -> not in the AI context. Structural restriction.
    """

    __tablename__ = "cohort_progress"
    __table_args__ = (UniqueConstraint("cohort_id", "lesson_id", name="uq_progress"),)

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    global_position: Mapped[int] = mapped_column(Integer, default=0)  # linear position completed

    cohort: Mapped[Cohort] = relationship(back_populates="progress")
