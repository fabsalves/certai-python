"""Área Custos: gasto de IA agregado por turma, aluno e aula.

Somente org_admin (e superadmin com organização selecionada). Período e modelo são filtro de banco;
busca/trilha/paginação ficam no client, como nas demais listagens.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import OrgIdQuery, org_id_for_product, require_roles
from app.models.user import Role, User
from app.schemas import (
    CohortCostDetailOut,
    CohortsCostOut,
    StudentCostDetailOut,
)
from app.services.usage.read_service import UsageCostReadService, default_window

router = APIRouter(prefix="/costs", tags=["costs"])

can_view_costs = require_roles(Role.ORG_ADMIN, Role.SUPERADMIN)

DateFrom = Annotated[datetime | None, Query(alias="from")]
DateTo = Annotated[datetime | None, Query(alias="to")]
ModelFilter = Annotated[str | None, Query(alias="model")]


def _clean_model(model: str | None) -> str | None:
    value = (model or "").strip()
    return value or None


@router.get("/cohorts", response_model=CohortsCostOut, dependencies=[Depends(can_view_costs)])
async def list_cohort_costs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_view_costs)],
    date_from: DateFrom = None,
    date_to: DateTo = None,
    model: ModelFilter = None,
    selected_org_id: OrgIdQuery = None,
) -> CohortsCostOut:
    start, end = default_window(date_from, date_to)
    model_filter = _clean_model(model)
    org_id = org_id_for_product(user, selected_org_id)
    result = await UsageCostReadService.list_cohorts(
        db, date_from=start, date_to=end, model=model_filter, organization_id=org_id
    )
    return CohortsCostOut(
        cohorts=result.cohorts,
        total_cost_usd=float(result.total_cost_usd),
        unattributed_cost_usd=float(result.unattributed_cost_usd),
        unpriced_events=result.unpriced_events,
        models=result.models,
        usd_brl_rate=settings.USD_BRL_RATE,
        period_from=start,
        period_to=end,
    )


@router.get(
    "/cohorts/{cohort_id}",
    response_model=CohortCostDetailOut,
    dependencies=[Depends(can_view_costs)],
)
async def cohort_cost_detail(
    cohort_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_view_costs)],
    date_from: DateFrom = None,
    date_to: DateTo = None,
    model: ModelFilter = None,
    selected_org_id: OrgIdQuery = None,
) -> CohortCostDetailOut:
    start, end = default_window(date_from, date_to)
    model_filter = _clean_model(model)
    org_id = org_id_for_product(user, selected_org_id)
    detail = await UsageCostReadService.cohort_detail(
        db,
        cohort_id=cohort_id,
        date_from=start,
        date_to=end,
        model=model_filter,
        organization_id=org_id,
    )
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turma não encontrada")
    return CohortCostDetailOut(
        cohort_id=detail.cohort_id,
        cohort_title=detail.cohort_title,
        track_title=detail.track_title,
        voice_minutes_est=detail.voice_minutes_est,
        cost_usd=float(detail.cost_usd),
        unpriced_events=detail.unpriced_events,
        by_kind=detail.by_kind,
        students=detail.students,
        models=detail.models,
        usd_brl_rate=settings.USD_BRL_RATE,
        period_from=start,
        period_to=end,
    )


@router.get(
    "/cohorts/{cohort_id}/students/{student_id}",
    response_model=StudentCostDetailOut,
    dependencies=[Depends(can_view_costs)],
)
async def student_cost_detail(
    cohort_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_view_costs)],
    date_from: DateFrom = None,
    date_to: DateTo = None,
    model: ModelFilter = None,
    selected_org_id: OrgIdQuery = None,
) -> StudentCostDetailOut:
    start, end = default_window(date_from, date_to)
    model_filter = _clean_model(model)
    org_id = org_id_for_product(user, selected_org_id)
    detail = await UsageCostReadService.student_detail(
        db,
        cohort_id=cohort_id,
        student_id=student_id,
        date_from=start,
        date_to=end,
        model=model_filter,
        organization_id=org_id,
    )
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno ou turma não encontrado")
    return StudentCostDetailOut(
        cohort_id=detail.cohort_id,
        cohort_title=detail.cohort_title,
        student_id=detail.student_id,
        student_name=detail.student_name,
        voice_minutes_est=detail.voice_minutes_est,
        cost_usd=float(detail.cost_usd),
        unpriced_events=detail.unpriced_events,
        by_kind=detail.by_kind,
        lessons=detail.lessons,
        models=detail.models,
        usd_brl_rate=settings.USD_BRL_RATE,
        period_from=start,
        period_to=end,
    )
