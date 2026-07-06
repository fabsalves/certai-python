import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(str, enum.Enum):
    """System roles. Each one determines allowed routes and actions."""

    ADMIN = "admin"            # platform-wide management
    DESIGNER = "designer"      # defines tracks, modules and lessons
    PROFESSOR = "professor"    # teaches, signals lesson completion per cohort
    STUDENT = "student"        # consumes the track, talks to the agent


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=20), default=Role.STUDENT, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whatsapp: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
