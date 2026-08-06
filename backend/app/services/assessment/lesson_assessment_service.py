"""Lesson-scope student assessment — external evaluator role (not Lira)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentScope, CohortLessonNote, MicroScore
from app.models.student_progress import StudentLessonProgress, StudentLessonProgressStatus
from app.models.track import Lesson
from app.services.assessment.evaluator import (
    format_micro_scores,
    run_evaluator_and_persist,
)
from app.services.cohort import ModuleClassService
from app.services.conversation_service import list_lesson_messages


def _format_conversation(messages: list) -> str:
    if not messages:
        return "(nenhuma mensagem nesta aula)"
    lines: list[str] = []
    for msg in messages:
        author = msg.author.value if hasattr(msg.author, "value") else str(msg.author)
        lines.append(f"[{author}] {msg.content}")
    return "\n".join(lines)


def _format_cohort_note(note: CohortLessonNote | None) -> str:
    if note is None:
        return "(sem relato do professor para esta turma/aula)"
    return (
        f"## Resumo\n{note.summary or '(vazio)'}\n\n"
        f"## Pontos pouco claros\n{note.unclear_points or '(vazio)'}\n\n"
        f"## Base de conhecimento do anexo\n{note.attachment_knowledge_base or '(vazio)'}\n\n"
        f"## Transcrição / relato do professor\n{note.professor_transcript or '(vazio)'}"
    )


def _lesson_closure_block(
    progress: StudentLessonProgress | None,
    *,
    message_count: int,
    score_count: int,
) -> str:
    if progress is None:
        status_label = "desconhecido (sem progresso registrado)"
        how = "Sem registro de como a aula foi encerrada."
    elif progress.status == StudentLessonProgressStatus.CONCLUIDA:
        status_label = "concluida (aluno finalizou com a Lira)"
        how = "Há intenção explícita de conclusão; julgue a evidência disponível."
    elif progress.status == StudentLessonProgressStatus.ENCERRADA_POR_AVANCO:
        status_label = "encerrada_por_avanco (turma avançou sem conclude)"
        how = (
            "A aula fechou porque a turma avançou. Se a conversa ou os "
            "micro-scores forem vazios ou insuficientes, use level null e "
            "registre a ausência em gaps — não invente compreensão."
        )
    else:
        status_label = progress.status.value
        how = "Julgue apenas com a evidência listada abaixo."

    return (
        f"Status do progresso do aluno: {status_label}\n"
        f"Mensagens na conversa: {message_count}\n"
        f"Micro-scores registrados: {score_count}\n"
        f"{how}"
    )


def _build_user_prompt(
    *,
    lesson_title: str,
    lesson_content: str,
    closure_block: str,
    note_block: str,
    micro_scores_block: str,
    conversation_block: str,
) -> str:
    return (
        f"# Escopo: aula\n"
        f"# Aula: {lesson_title}\n\n"
        f"## Como esta aula foi encerrada para o aluno\n{closure_block}\n\n"
        f"## Material da aula\n{lesson_content or '(sem conteúdo cadastrado)'}\n\n"
        f"## Escopo da turma (relato do professor)\n{note_block}\n\n"
        f"## Micro-scores do aluno nesta aula\n{micro_scores_block}\n\n"
        f"## Conversa do aluno nesta aula\n{conversation_block}"
    )


class LessonAssessmentService:
    @staticmethod
    async def assess(
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ):
        """Build lesson inputs (incl. conversation), call evaluator, persist."""
        lesson = await db.get(Lesson, lesson_id)
        if lesson is None:
            raise ValueError(f"Lesson not found: {lesson_id}")

        # The report of this student's own professor -- never another class's.
        module_class = await ModuleClassService.resolve_for_student(
            db, cohort_id, lesson.module_id, student_id
        )
        note = None
        if module_class is not None:
            note = await db.scalar(
                select(CohortLessonNote)
                .where(
                    CohortLessonNote.cohort_id == cohort_id,
                    CohortLessonNote.lesson_id == lesson_id,
                    CohortLessonNote.module_professor_id == module_class.id,
                )
                .order_by(CohortLessonNote.created_at.desc())
                .limit(1)
            )

        progress = await db.scalar(
            select(StudentLessonProgress).where(
                StudentLessonProgress.cohort_id == cohort_id,
                StudentLessonProgress.student_id == student_id,
                StudentLessonProgress.lesson_id == lesson_id,
            )
        )

        scores = (
            await db.scalars(
                select(MicroScore)
                .where(
                    MicroScore.cohort_id == cohort_id,
                    MicroScore.student_id == student_id,
                    MicroScore.lesson_id == lesson_id,
                )
                .order_by(MicroScore.created_at)
            )
        ).all()

        messages = await list_lesson_messages(db, cohort_id, student_id, lesson_id)
        score_list = list(scores)
        message_list = list(messages)

        user_prompt = _build_user_prompt(
            lesson_title=lesson.title,
            lesson_content=lesson.content,
            closure_block=_lesson_closure_block(
                progress,
                message_count=len(message_list),
                score_count=len(score_list),
            ),
            note_block=_format_cohort_note(note),
            micro_scores_block=format_micro_scores(
                score_list,
                empty_label="(nenhum micro-score registrado nesta aula)",
            ),
            conversation_block=_format_conversation(message_list),
        )

        return await run_evaluator_and_persist(
            db,
            cohort_id=cohort_id,
            student_id=student_id,
            scope=AssessmentScope.LESSON,
            user_prompt=user_prompt,
            lesson_id=lesson_id,
            module_id=None,
            track_id=None,
            log_context=(
                f"cohort={cohort_id} student={student_id} lesson={lesson_id}"
            ),
        )
