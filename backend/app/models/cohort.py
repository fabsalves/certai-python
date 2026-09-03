import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Cohort(Base):
    """Group of students going through a track. Progression is per cohort."""

    __tablename__ = "cohorts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="RESTRICT"), index=True
    )
    # A test cohort: its progression can be rewound (see SandboxService), so the
    # team can run the real cycle in production over and over.
    #
    # Set at creation and never changed -- not by a validation someone could work
    # around, but because the field does not exist in `CohortUpdate`. There is no
    # contract through which to flip it, so a real cohort created without the mark
    # can never become rewindable. Restriction as structure.
    is_sandbox: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
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
    """A teaching class: professor + module + cohort.

    A module may have several of these. When it has more than one, the enrolled
    students are split between them (see CohortModuleStudent) and each professor
    closes lessons for their own group only. With a single professor the whole
    cohort is their group and no roster exists.
    """

    __tablename__ = "cohort_module_professors"
    __table_args__ = (
        UniqueConstraint(
            "cohort_id", "module_id", "professor_id", name="uq_cohort_module_professor"
        ),
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
    students: Mapped[list["CohortModuleStudent"]] = relationship(
        back_populates="module_professor", cascade="all, delete-orphan"
    )


class CohortModuleStudent(Base):
    """Which students study a module with which professor.

    Only written when the module has more than one professor. A student belongs
    to a single class per module -- enforced by the service layer, which always
    replaces the whole module roster in one go.
    """

    __tablename__ = "cohort_module_students"
    __table_args__ = (
        UniqueConstraint(
            "module_professor_id", "student_id", name="uq_cohort_module_student"
        ),
    )

    module_professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohort_module_professors.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    module_professor: Mapped[CohortModuleProfessor] = relationship(
        back_populates="students"
    )


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
    """Lessons a class has studied. Written when its professor signals completion.

    The existence of a row here is what unlocks the lesson context for that
    class's students. A future lesson has no row -> not in the AI context.
    Structural restriction.
    """

    __tablename__ = "cohort_progress"
    __table_args__ = (
        UniqueConstraint(
            "cohort_id", "lesson_id", "module_professor_id", name="uq_progress"
        ),
    )

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cohorts.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    module_professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cohort_module_professors.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    global_position: Mapped[int] = mapped_column(Integer, default=0)  # position within the class

    cohort: Mapped[Cohort] = relationship(back_populates="progress")
