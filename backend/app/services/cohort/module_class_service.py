"""Resolution of teaching classes (cohort + module + professor).

A module may be taught by several professors, each to their own group of the
cohort's students. This service is the only place that knows the shortcut that
keeps the common case simple: when a module has a single professor, the whole
cohort is their class and no roster is stored.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import (
    CohortModuleProfessor,
    CohortModuleStudent,
    Enrollment,
)


class ModuleClassService:
    @staticmethod
    async def classes_of_module(
        db: AsyncSession, cohort_id: uuid.UUID, module_id: uuid.UUID
    ) -> list[CohortModuleProfessor]:
        return list(
            (
                await db.scalars(
                    select(CohortModuleProfessor).where(
                        CohortModuleProfessor.cohort_id == cohort_id,
                        CohortModuleProfessor.module_id == module_id,
                    )
                )
            ).all()
        )

    @staticmethod
    async def class_of_professor(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        module_id: uuid.UUID,
        professor_id: uuid.UUID,
    ) -> CohortModuleProfessor | None:
        return await db.scalar(
            select(CohortModuleProfessor).where(
                CohortModuleProfessor.cohort_id == cohort_id,
                CohortModuleProfessor.module_id == module_id,
                CohortModuleProfessor.professor_id == professor_id,
            )
        )

    @staticmethod
    async def classes_of_professor(
        db: AsyncSession, cohort_id: uuid.UUID, professor_id: uuid.UUID
    ) -> list[CohortModuleProfessor]:
        return list(
            (
                await db.scalars(
                    select(CohortModuleProfessor).where(
                        CohortModuleProfessor.cohort_id == cohort_id,
                        CohortModuleProfessor.professor_id == professor_id,
                    )
                )
            ).all()
        )

    @staticmethod
    async def resolve_for_student(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        module_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> CohortModuleProfessor | None:
        """The class a student belongs to in this module, if any."""
        classes = await ModuleClassService.classes_of_module(db, cohort_id, module_id)
        if not classes:
            return None
        if len(classes) == 1:
            return classes[0]

        return await db.scalar(
            select(CohortModuleProfessor)
            .join(
                CohortModuleStudent,
                CohortModuleStudent.module_professor_id == CohortModuleProfessor.id,
            )
            .where(
                CohortModuleProfessor.cohort_id == cohort_id,
                CohortModuleProfessor.module_id == module_id,
                CohortModuleStudent.student_id == student_id,
            )
        )

    @staticmethod
    async def student_ids_of(
        db: AsyncSession, module_class: CohortModuleProfessor
    ) -> list[uuid.UUID]:
        """Students taught by this class. The whole cohort when it is the only one."""
        enrolled = await ModuleClassService._enrolled_student_ids(
            db, module_class.cohort_id
        )
        classes = await ModuleClassService.classes_of_module(
            db, module_class.cohort_id, module_class.module_id
        )
        if len(classes) <= 1:
            return enrolled

        rostered = set(
            (
                await db.scalars(
                    select(CohortModuleStudent.student_id).where(
                        CohortModuleStudent.module_professor_id == module_class.id
                    )
                )
            ).all()
        )
        return [student_id for student_id in enrolled if student_id in rostered]

    @staticmethod
    async def unassigned_student_ids(
        db: AsyncSession, cohort_id: uuid.UUID, module_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Enrolled students with no class in a module taught by several professors."""
        classes = await ModuleClassService.classes_of_module(db, cohort_id, module_id)
        if len(classes) <= 1:
            return []

        enrolled = await ModuleClassService._enrolled_student_ids(db, cohort_id)
        assigned = set(
            (
                await db.scalars(
                    select(CohortModuleStudent.student_id).where(
                        CohortModuleStudent.module_professor_id.in_(
                            [item.id for item in classes]
                        )
                    )
                )
            ).all()
        )
        return [student_id for student_id in enrolled if student_id not in assigned]

    @staticmethod
    async def classes_by_module_for_student(
        db: AsyncSession, cohort_id: uuid.UUID, student_id: uuid.UUID
    ) -> dict[uuid.UUID, uuid.UUID]:
        """module_id -> class id, for every module the student studies in this cohort."""
        classes = list(
            (
                await db.scalars(
                    select(CohortModuleProfessor).where(
                        CohortModuleProfessor.cohort_id == cohort_id
                    )
                )
            ).all()
        )
        if not classes:
            return {}

        by_module: dict[uuid.UUID, list[CohortModuleProfessor]] = {}
        for item in classes:
            by_module.setdefault(item.module_id, []).append(item)

        rostered = set(
            (
                await db.scalars(
                    select(CohortModuleStudent.module_professor_id).where(
                        CohortModuleStudent.student_id == student_id,
                        CohortModuleStudent.module_professor_id.in_(
                            [item.id for item in classes]
                        ),
                    )
                )
            ).all()
        )

        resolved: dict[uuid.UUID, uuid.UUID] = {}
        for module_id, module_classes in by_module.items():
            if len(module_classes) == 1:
                resolved[module_id] = module_classes[0].id
                continue
            for item in module_classes:
                if item.id in rostered:
                    resolved[module_id] = item.id
                    break
        return resolved

    @staticmethod
    async def replace_module_roster(
        db: AsyncSession,
        classes: list[CohortModuleProfessor],
        student_ids_by_class: dict[uuid.UUID, list[uuid.UUID]],
    ) -> list[tuple[CohortModuleProfessor, uuid.UUID]]:
        """Rewrite the roster of a module in one go -- the guarantee that a student
        belongs to a single class per module.

        Returns (class, student_id) pairs that were newly assigned (for mid-join
        catch-up). Empty when the module has a single professor (no roster).
        """
        class_ids = [item.id for item in classes]
        previous: dict[uuid.UUID, set[uuid.UUID]] = {item.id: set() for item in classes}
        if class_ids:
            existing = (
                await db.scalars(
                    select(CohortModuleStudent).where(
                        CohortModuleStudent.module_professor_id.in_(class_ids)
                    )
                )
            ).all()
            for row in existing:
                previous.setdefault(row.module_professor_id, set()).add(row.student_id)
                await db.delete(row)
            await db.flush()

        if len(classes) <= 1:
            return []

        additions: list[tuple[CohortModuleProfessor, uuid.UUID]] = []
        for module_class in classes:
            wanted = list(
                dict.fromkeys(student_ids_by_class.get(module_class.id, []))
            )
            prev = previous.get(module_class.id, set())
            for student_id in wanted:
                db.add(
                    CohortModuleStudent(
                        module_professor_id=module_class.id, student_id=student_id
                    )
                )
                if student_id not in prev:
                    additions.append((module_class, student_id))
        await db.flush()
        return additions

    @staticmethod
    async def _enrolled_student_ids(
        db: AsyncSession, cohort_id: uuid.UUID
    ) -> list[uuid.UUID]:
        return list(
            (
                await db.scalars(
                    select(Enrollment.student_id).where(
                        Enrollment.cohort_id == cohort_id
                    )
                )
            ).all()
        )
