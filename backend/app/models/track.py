import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ModuleLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Track(Base):
    """Learning journey. Created by a designer. Static structure."""

    __tablename__ = "tracks"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    competency: Mapped[str] = mapped_column(String(255), default="")  # what the student must absorb
    published: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    material_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    material_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    modules: Mapped[list["Module"]] = relationship(
        back_populates="track", order_by="Module.position", cascade="all, delete-orphan"
    )


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("track_id", "position", name="uq_module_position"),)

    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[ModuleLevel] = mapped_column(
        Enum(ModuleLevel, native_enum=False, length=20), default=ModuleLevel.BEGINNER
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # place in the sequence
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    track: Mapped[Track] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module", order_by="Lesson.position", cascade="all, delete-orphan"
    )


class Lesson(Base):
    """Content unit. Immutable during execution; fixed sequence."""

    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_lesson_position"),)

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")  # pre-registered material
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    module: Mapped[Module] = relationship(back_populates="lessons")
