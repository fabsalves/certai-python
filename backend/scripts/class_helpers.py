"""Class resolution for the verification scripts.

The scripts drive the flow directly, without the HTTP layer that normally
resolves which class a professor is closing a lesson for. These helpers pick
the class of the lesson's module -- the seed keeps one professor per module,
so there is exactly one.
"""

from __future__ import annotations

import uuid

from app.models.track import Lesson
from app.services.cohort import ModuleClassService


async def lesson_class(db, cohort_id: uuid.UUID, lesson_id: uuid.UUID):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise RuntimeError(f"Aula não encontrada: {lesson_id}")

    classes = await ModuleClassService.classes_of_module(db, cohort_id, lesson.module_id)
    if not classes:
        raise RuntimeError("Módulo da aula sem professor atribuído — rode bin/db-reset")
    return classes[0]


async def lesson_class_id(db, cohort_id: uuid.UUID, lesson_id: uuid.UUID) -> uuid.UUID:
    return (await lesson_class(db, cohort_id, lesson_id)).id


async def lesson_student_ids(
    db, cohort_id: uuid.UUID, lesson_id: uuid.UUID
) -> list[uuid.UUID]:
    module_class = await lesson_class(db, cohort_id, lesson_id)
    return await ModuleClassService.student_ids_of(db, module_class)
