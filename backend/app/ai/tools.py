"""The engine's tool arsenal.

Philosophy: the AI decides everything. Tools are capabilities -- the richer, the
better. The code here only executes the effect the AI chose, with no heuristics,
no per-word inference, no flow determinism.

Each tool declares its schema (for the OpenAI API) and an async implementation.
The engine calls `dispatch()` when the AI requests a tool and feeds the result
back to the AI to keep reasoning (including scope escalation).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.models.assessment import Level, MicroScore

# Schemas expostos à OpenAI (function calling). Descrições enxutas, sem "regras".
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "escalate_scope",
            "description": (
                "Fetch context one level up (module or track) when the student asks "
                "something outside the current lesson scope. The result returns to you "
                "to keep answering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_level": {"type": "string", "enum": ["module", "track"]},
                    "reason": {"type": "string"},
                },
                "required": ["target_level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_understanding",
            "description": (
                "Record a qualitative micro-score of the student's understanding of a "
                "competency. Use it when there is enough signal in the conversation -- "
                "not on every message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "competency": {"type": "string"},
                    "level": {
                        "type": "string",
                        "enum": ["very_low", "low", "medium", "high"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["competency", "level", "evidence"],
            },
        },
    },
]


class ToolContext:
    """State the tools need to act -- always tied to the cohort (segregation)."""

    def __init__(
        self,
        db: AsyncSession,
        cohort_id: uuid.UUID,
        student_id: uuid.UUID | None,
        lesson_id: uuid.UUID | None,
    ):
        self.db = db
        self.cohort_id = cohort_id
        self.student_id = student_id
        self.lesson_id = lesson_id
        self.builder = ContextBuilder(db)


async def dispatch(name: str, args: dict[str, Any], ctx: ToolContext) -> str:
    """Run the tool requested by the AI and return text to feed reasoning back."""
    if name == "escalate_scope":
        return await _escalate_scope(args, ctx)
    if name == "score_understanding":
        return await _score_understanding(args, ctx)
    return f"Unknown tool: {name}"


async def _escalate_scope(args: dict[str, Any], ctx: ToolContext) -> str:
    level = args.get("target_level", "track")
    if level == "module" and ctx.lesson_id:
        bundle = await ctx.builder.build_module(ctx.cohort_id, ctx.lesson_id)
    else:
        bundle = await ctx.builder.build_track(ctx.cohort_id)
    return bundle.to_system_blocks()


async def _score_understanding(args: dict[str, Any], ctx: ToolContext) -> str:
    if ctx.student_id is None:
        return "No student in context; score ignored."
    score = MicroScore(
        cohort_id=ctx.cohort_id,
        student_id=ctx.student_id,
        lesson_id=ctx.lesson_id,
        competency=args["competency"],
        level=Level(args["level"]),
        evidence=args.get("evidence", ""),
    )
    ctx.db.add(score)
    await ctx.db.flush()
    return f"Micro-score recorded: {args['competency']} = {args['level']}."
