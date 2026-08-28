"""Shared guards for org user create/update."""
from uuid import UUID

from fastapi import HTTPException, status

from app.models.user import Role, User

ASSIGNABLE_ROLES = {Role.ORG_ADMIN, Role.PROFESSOR, Role.STUDENT}
STAFF_ROLES = {Role.ORG_ADMIN, Role.PROFESSOR}


def assert_assignable_role(role: Role) -> None:
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Papel inválido para esta organização.",
        )


def assert_same_org(actor: User, target_org_id: UUID | None) -> None:
    if actor.role == Role.SUPERADMIN:
        return
    if actor.organization_id is None or target_org_id != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")


def validate_user_update(actor: User, target: User, *, role: Role | None, is_active: bool | None) -> None:
    if role is not None:
        assert_assignable_role(role)
        if target.role == Role.STUDENT or role == Role.STUDENT:
            if target.role != role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Papel de aluno não pode ser alterado.",
                )
        if role not in STAFF_ROLES and role != Role.STUDENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Papel inválido.")
    if actor.id != target.id:
        return
    if role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar o seu próprio papel.",
        )
    if is_active is not None and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode desativar a sua própria conta.",
        )
