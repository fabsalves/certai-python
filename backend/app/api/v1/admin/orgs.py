import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_org_admin, require_org_scope, require_roles, require_superadmin
from app.core.passwords import validate_new_password
from app.core.security import generate_password, hash_password
from app.integrations.ai.catalog import catalog_payload, validate_model_field
from app.models import Organization, OrgSettings, User
from app.models.user import Role
from app.schemas import (
    AdminUserOut,
    CredentialTestRequest,
    CredentialTestResponse,
    OrgCreate,
    OrgDetailOut,
    OrgListItem,
    OrgSettingsOut,
    OrgSettingsUpdate,
    PasswordUpdate,
    SettingsCatalogOut,
    UserCreate,
    UserCreatedOut,
    UserOut,
    UserUpdate,
)
from app.services.access import assert_assignable_role, validate_user_update
from app.services.credential_tests import CredentialTestError, run_credential_test
from app.services.org_config import (
    PLAIN_FIELDS,
    SECRET_FIELDS,
    get_or_create_org_settings,
    resolve_org_config,
    update_org_settings,
)

MODEL_FIELDS = (
    "engine_model",
    "humanizer_model",
    "evaluator_model",
    "groq_transcribe_model",
    "openai_realtime_model",
    "openai_realtime_voice",
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    n = 2
    while await db.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base}-{n}"
        n += 1
    return slug


def _settings_to_out(config, *, slug: str = "", org_row=None) -> OrgSettingsOut:
    public = config.public_settings(org_row=org_row)
    return OrgSettingsOut(
        organization_slug=slug,
        webhook_base_url=settings.PUBLIC_API_BASE_URL.rstrip("/"),
        **public,
    )


async def _apply_settings(
    db: AsyncSession, org_id: uuid.UUID, payload: OrgSettingsUpdate
) -> OrgSettingsOut:
    plain = {
        key: getattr(payload, key)
        for key in PLAIN_FIELDS
        if getattr(payload, key) is not None
    }
    for key, value in list(plain.items()):
        if key not in MODEL_FIELDS:
            continue
        try:
            plain[key] = validate_model_field(key, value)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    secret = {
        key: getattr(payload, key)
        for key in SECRET_FIELDS
        if getattr(payload, key) is not None and str(getattr(payload, key)).strip()
    }
    clear = {key for key in payload.clear_secrets if key in SECRET_FIELDS}
    config = await update_org_settings(
        db,
        org_id=org_id,
        plain_updates=plain or None,
        secret_updates=secret or None,
        clear_secrets=clear or None,
    )
    org = await db.get(Organization, org_id)
    row = await get_or_create_org_settings(db, org_id)
    await db.commit()
    return _settings_to_out(config, slug=org.slug if org else "", org_row=row)


async def _test_credential(
    db: AsyncSession, org_id: uuid.UUID, payload: CredentialTestRequest
) -> CredentialTestResponse:
    config = await resolve_org_config(db, org_id)
    try:
        message = await run_credential_test(field=payload.field, config=config, value=payload.value)
    except CredentialTestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível contactar o provedor. Tente novamente.",
        ) from exc
    return CredentialTestResponse(message=message)


async def _org_or_404(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organização não encontrada.")
    return org


def _admin_user_item(user: User, org_name: str | None) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        whatsapp=user.whatsapp,
        organization_id=user.organization_id,
        organization_name=org_name,
    )


@router.get("/orgs", response_model=list[OrgListItem])
async def list_organizations(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> list[OrgListItem]:
    rows = await db.execute(
        select(Organization, func.count(User.id).label("user_count"))
        .outerjoin(User, User.organization_id == Organization.id)
        .group_by(Organization.id)
        .order_by(Organization.created_at)
    )
    items: list[OrgListItem] = []
    for org, user_count in rows.all():
        items.append(
            OrgListItem(
                id=org.id,
                name=org.name,
                slug=org.slug,
                is_active=org.is_active,
                user_count=int(user_count),
                created_at=org.created_at,
            )
        )
    return items


@router.post("/orgs", response_model=OrgDetailOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> OrgDetailOut:
    slug = await _unique_slug(db, payload.slug or _slugify(payload.name))
    org = Organization(name=payload.name, slug=slug)
    db.add(org)
    await db.flush()
    db.add(OrgSettings(organization_id=org.id, settings={}, secrets={}))
    await db.commit()
    await db.refresh(org)
    config = await resolve_org_config(db, org.id)
    row = await get_or_create_org_settings(db, org.id)
    return OrgDetailOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        user_count=0,
        created_at=org.created_at,
        settings=_settings_to_out(config, slug=org.slug, org_row=row),
    )


@router.get("/orgs/{org_id}", response_model=OrgDetailOut)
async def get_organization(
    org_id: uuid.UUID,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> OrgDetailOut:
    org = await _org_or_404(db, org_id)
    user_count = await db.scalar(select(func.count(User.id)).where(User.organization_id == org_id))
    config = await resolve_org_config(db, org_id)
    row = await get_or_create_org_settings(db, org_id)
    return OrgDetailOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        user_count=int(user_count or 0),
        created_at=org.created_at,
        settings=_settings_to_out(config, slug=org.slug, org_row=row),
    )


@router.patch("/orgs/{org_id}/settings", response_model=OrgSettingsOut)
async def update_organization_settings(
    org_id: uuid.UUID,
    payload: OrgSettingsUpdate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> OrgSettingsOut:
    await _org_or_404(db, org_id)
    return await _apply_settings(db, org_id, payload)


@router.post("/orgs/{org_id}/settings/test-credential", response_model=CredentialTestResponse)
async def test_organization_credential(
    org_id: uuid.UUID,
    payload: CredentialTestRequest,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> CredentialTestResponse:
    await _org_or_404(db, org_id)
    return await _test_credential(db, org_id, payload)


@router.get("/users", response_model=list[AdminUserOut])
async def list_all_users(
    org_id: uuid.UUID | None = Query(default=None),
    role: Role | None = Query(default=None),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserOut]:
    stmt = (
        select(User, Organization.name)
        .outerjoin(Organization, Organization.id == User.organization_id)
        .order_by(User.created_at)
    )
    if org_id is not None:
        stmt = stmt.where(User.organization_id == org_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    rows = await db.execute(stmt)
    return [_admin_user_item(user, org_name) for user, org_name in rows.all()]


@router.get("/orgs/{org_id}/users", response_model=list[AdminUserOut])
async def list_organization_users(
    org_id: uuid.UUID,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserOut]:
    org = await _org_or_404(db, org_id)
    rows = await db.scalars(
        select(User).where(User.organization_id == org_id).order_by(User.created_at)
    )
    return [_admin_user_item(user, org.name) for user in rows]


@router.post(
    "/orgs/{org_id}/users",
    response_model=UserCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_user(
    org_id: uuid.UUID,
    payload: UserCreate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> UserCreatedOut:
    await _org_or_404(db, org_id)
    assert_assignable_role(payload.role)
    if await db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    if payload.whatsapp and await db.scalar(select(User).where(User.whatsapp == payload.whatsapp)):
        raise HTTPException(status.HTTP_409_CONFLICT, "WhatsApp já cadastrado")
    plain = generate_password()
    user = User(
        organization_id=org_id,
        email=payload.email,
        name=payload.name,
        role=payload.role,
        hashed_password=hash_password(plain),
        whatsapp=payload.whatsapp,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    created = UserCreatedOut.model_validate(user)
    if payload.role != Role.STUDENT:
        return created.model_copy(update={"initial_password": plain})
    return created


@router.patch("/orgs/{org_id}/users/{user_id}", response_model=AdminUserOut)
async def update_organization_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserOut:
    org = await _org_or_404(db, org_id)
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == org_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    validate_user_update(admin, user, role=payload.role, is_active=payload.is_active)
    user.name = payload.name
    if payload.email != user.email:
        if await db.scalar(select(User).where(User.email == payload.email)):
            raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
        user.email = payload.email
    if payload.whatsapp is not None:
        user.whatsapp = payload.whatsapp
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return _admin_user_item(user, org.name)


@router.patch("/orgs/{org_id}/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_organization_user_password(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: PasswordUpdate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        validate_new_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await _org_or_404(db, org_id)
    user = await db.scalar(select(User).where(User.id == user_id, User.organization_id == org_id))
    if user is None or user.role == Role.SUPERADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    user.hashed_password = hash_password(payload.password)
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()


# --- org_admin settings of own org ---
settings_router = APIRouter(prefix="/settings", tags=["settings"])


@settings_router.get("/catalog", response_model=SettingsCatalogOut)
async def get_settings_catalog(
    _: User = Depends(require_roles(Role.ORG_ADMIN, Role.SUPERADMIN)),
) -> SettingsCatalogOut:
    return SettingsCatalogOut(**catalog_payload())


@settings_router.get("", response_model=OrgSettingsOut)
async def get_own_org_settings(
    admin: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgSettingsOut:
    org_id = require_org_scope(admin)
    org = await db.get(Organization, org_id)
    config = await resolve_org_config(db, org_id)
    row = await get_or_create_org_settings(db, org_id)
    return _settings_to_out(config, slug=org.slug if org else "", org_row=row)


@settings_router.patch("", response_model=OrgSettingsOut)
async def update_own_org_settings(
    payload: OrgSettingsUpdate,
    admin: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgSettingsOut:
    org_id = require_org_scope(admin)
    return await _apply_settings(db, org_id, payload)


@settings_router.post("/test-credential", response_model=CredentialTestResponse)
async def test_own_org_credential(
    payload: CredentialTestRequest,
    admin: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
) -> CredentialTestResponse:
    org_id = require_org_scope(admin)
    return await _test_credential(db, org_id, payload)
