import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.db_events import enqueue_after_commit
from app.core.deps import require_org_scope, require_roles
from app.models.cohort import CohortModuleProfessor
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.services.ingestion.content_source_import_service import import_catalog_source
from app.services.storage import get_storage
from app.services.storage.download import file_response
from app.services.track_structure import ensure_unique_lesson_title, ensure_unique_module_title
from app.services.upload_validation import (
    MATERIAL_MAX_BYTES,
    TRACK_MATERIAL_BY_EXT,
    read_upload,
    resolve_allowed_type,
)
from app.schemas import (
    ImportTextOut,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    ModuleCreate,
    ModuleOut,
    ModuleUpdate,
    TrackCreate,
    TrackOut,
    TrackUpdate,
)

router = APIRouter(prefix="/tracks", tags=["tracks"])

can_edit = require_roles(Role.ORG_ADMIN)


async def _get_track(db: AsyncSession, track_id: uuid.UUID, org_id: uuid.UUID) -> Track:
    stmt = (
        select(Track)
        .where(Track.id == track_id, Track.organization_id == org_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    track = (await db.execute(stmt)).scalar_one_or_none()
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trilha não encontrada")
    return track


async def _get_module(db: AsyncSession, module_id: uuid.UUID, org_id: uuid.UUID) -> Module:
    stmt = (
        select(Module)
        .join(Track, Module.track_id == Track.id)
        .where(Module.id == module_id, Track.organization_id == org_id)
        .options(selectinload(Module.lessons))
    )
    module = (await db.execute(stmt)).scalar_one_or_none()
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo não encontrado")
    return module


async def _get_lesson(db: AsyncSession, lesson_id: uuid.UUID, org_id: uuid.UUID) -> Lesson:
    stmt = (
        select(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .join(Track, Module.track_id == Track.id)
        .where(Lesson.id == lesson_id, Track.organization_id == org_id)
    )
    lesson = (await db.execute(stmt)).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")
    return lesson


@router.get("", response_model=list[TrackOut], dependencies=[Depends(can_edit)])
async def list_tracks(user: Annotated[User, Depends(can_edit)], db: Annotated[AsyncSession, Depends(get_db)]):
    org_id = require_org_scope(user)
    stmt = (
        select(Track)
        .where(Track.organization_id == org_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    return (await db.execute(stmt)).scalars().all()


@router.post(
    "/lessons/{lesson_id}/import-text",
    response_model=ImportTextOut,
    dependencies=[Depends(can_edit)],
)
async def import_text_for_lesson_content(
    lesson_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_edit)],
    source: Annotated[
        UploadFile,
        File(description="Áudio ou documento para preencher o conteúdo da aula"),
    ],
    base_text: Annotated[
        str | None,
        Form(
            description="Texto atual do campo (editor). Novo trecho é concatenado a este base.",
        ),
    ] = None,
):
    """Transcribe/extract and append into lesson content; persist latest source file."""
    org_id = require_org_scope(user)
    lesson = await _get_lesson(db, lesson_id, org_id)

    imported = await import_catalog_source(
        source,
        base_text=base_text,
        current_text=lesson.content,
        previous_storage_key=lesson.content_source_storage_key,
        storage_prefix=f"lessons/{lesson_id}/content-source",
        organization_id=org_id,
        db=db,
    )
    lesson.content = imported.text
    lesson.content_source_storage_key = imported.storage_key
    lesson.content_source_filename = imported.filename
    lesson.content_source_content_type = imported.content_type
    lesson.content_source_kind = imported.kind
    await db.flush()
    return imported.to_out()


@router.get(
    "/lessons/{lesson_id}/content-source",
    dependencies=[Depends(can_edit)],
)
async def download_lesson_content_source(
    lesson_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await _get_lesson(db, lesson_id, require_org_scope(user))
    if not lesson.content_source_storage_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhum arquivo fonte nesta aula")
    return await file_response(
        storage_key=lesson.content_source_storage_key,
        filename=lesson.content_source_filename or "source",
        content_type=lesson.content_source_content_type,
    )


@router.get("/{track_id}", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def get_track(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await _get_track(db, track_id, require_org_scope(user))


@router.post("", response_model=TrackOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(can_edit)])
async def create_track(
    body: TrackCreate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = Track(**body.model_dump(), organization_id=require_org_scope(user))
    db.add(track)
    await db.flush()
    await db.refresh(track, ["modules"])
    return track


@router.patch("/{track_id}", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def update_track(
    track_id: uuid.UUID,
    body: TrackUpdate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id, require_org_scope(user))
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False:
        data["published"] = False
    for key, value in data.items():
        setattr(track, key, value)
    await db.flush()
    return await _get_track(db, track_id, require_org_scope(user))


@router.post("/{track_id}/publish", response_model=TrackOut,
             dependencies=[Depends(can_edit)])
async def publish_track(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id, require_org_scope(user))
    track.published = True
    await db.flush()
    return await _get_track(db, track_id, require_org_scope(user))


@router.post("/{track_id}/material", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def upload_track_material(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="PDF ou PPT da trilha")],
):
    """Attach or replace the single material file for a track (PDF/PPT/PPTX).
    The AI ingestion (macro track guide) runs asynchronously after commit."""
    track = await _get_track(db, track_id, require_org_scope(user))
    content_type, ext = resolve_allowed_type(file, TRACK_MATERIAL_BY_EXT)
    content = await read_upload(
        file,
        max_bytes=MATERIAL_MAX_BYTES,
        too_large_message="Arquivo muito grande (máx. 20 MB)",
    )

    storage = get_storage()
    if track.material_storage_key:
        await storage.delete(track.material_storage_key)

    key = f"tracks/{track_id}/material/{uuid.uuid4()}{ext}"
    await storage.save(content, key, content_type=content_type)

    track.material_storage_key = key
    track.material_filename = file.filename or f"material{ext}"
    track.material_content_type = content_type
    # New file invalidates any previous ingestion.
    track.material_extracted_text = ""
    track.material_guide = ""
    track.material_ingestion_status = "pending"
    await db.flush()

    from app.workers.tasks import ingest_track_material

    enqueue_after_commit(db, ingest_track_material, str(track_id))
    return await _get_track(db, track_id, require_org_scope(user))


@router.post(
    "/{track_id}/material/ingest",
    response_model=TrackOut,
    dependencies=[Depends(can_edit)],
)
async def reingest_track_material(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Re-enqueue the AI ingestion of the track material (legacy files or failures)."""
    track = await _get_track(db, track_id, require_org_scope(user))
    if not track.material_storage_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A trilha não possui material anexado")

    track.material_ingestion_status = "pending"
    await db.flush()

    from app.workers.tasks import ingest_track_material

    enqueue_after_commit(db, ingest_track_material, str(track_id))
    return await _get_track(db, track_id, require_org_scope(user))


@router.get("/{track_id}/material", dependencies=[Depends(can_edit)])
async def download_track_material(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id, require_org_scope(user))
    return await file_response(
        storage_key=track.material_storage_key,
        filename=track.material_filename or "material",
        content_type=track.material_content_type,
    )


@router.post(
    "/{track_id}/import-description",
    response_model=ImportTextOut,
    dependencies=[Depends(can_edit)],
)
async def import_text_for_track_description(
    track_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_edit)],
    source: Annotated[
        UploadFile,
        File(description="Áudio ou documento para preencher a descrição da trilha"),
    ],
    base_text: Annotated[
        str | None,
        Form(
            description="Texto atual do campo (editor). Novo trecho é concatenado a este base.",
        ),
    ] = None,
):
    """Transcribe/extract and append into track.description; persist latest source file.

    Distinct from track material (PDF/PPT for AI ingestion).
    """
    track = await _get_track(db, track_id, require_org_scope(user))
    imported = await import_catalog_source(
        source,
        base_text=base_text,
        current_text=track.description,
        previous_storage_key=track.description_source_storage_key,
        storage_prefix=f"tracks/{track_id}/description-source",
        organization_id=track.organization_id,
        db=db,
    )
    track.description = imported.text
    track.description_source_storage_key = imported.storage_key
    track.description_source_filename = imported.filename
    track.description_source_content_type = imported.content_type
    track.description_source_kind = imported.kind
    await db.flush()
    return imported.to_out()


@router.get(
    "/{track_id}/description-source",
    dependencies=[Depends(can_edit)],
)
async def download_track_description_source(
    track_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id, require_org_scope(user))
    if not track.description_source_storage_key:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nenhum arquivo fonte na descrição desta trilha"
        )
    return await file_response(
        storage_key=track.description_source_storage_key,
        filename=track.description_source_filename or "source",
        content_type=track.description_source_content_type,
    )


@router.post(
    "/modules/{module_id}/import-description",
    response_model=ImportTextOut,
    dependencies=[Depends(can_edit)],
)
async def import_text_for_module_description(
    module_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(can_edit)],
    source: Annotated[
        UploadFile,
        File(description="Áudio ou documento para preencher a descrição do módulo"),
    ],
    base_text: Annotated[
        str | None,
        Form(
            description="Texto atual do campo (editor). Novo trecho é concatenado a este base.",
        ),
    ] = None,
):
    """Transcribe/extract and append into module.description; persist latest source file."""
    org_id = require_org_scope(user)
    module = await _get_module(db, module_id, org_id)

    imported = await import_catalog_source(
        source,
        base_text=base_text,
        current_text=module.description,
        previous_storage_key=module.description_source_storage_key,
        storage_prefix=f"modules/{module_id}/description-source",
        organization_id=org_id,
        db=db,
    )
    module.description = imported.text
    module.description_source_storage_key = imported.storage_key
    module.description_source_filename = imported.filename
    module.description_source_content_type = imported.content_type
    module.description_source_kind = imported.kind
    await db.flush()
    return imported.to_out()


@router.get(
    "/modules/{module_id}/description-source",
    dependencies=[Depends(can_edit)],
)
async def download_module_description_source(
    module_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    module = await _get_module(db, module_id, require_org_scope(user))
    if not module.description_source_storage_key:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nenhum arquivo fonte na descrição deste módulo"
        )
    return await file_response(
        storage_key=module.description_source_storage_key,
        filename=module.description_source_filename or "source",
        content_type=module.description_source_content_type,
    )


@router.post("/{track_id}/modules", response_model=ModuleOut,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(can_edit)])
async def create_module(
    track_id: uuid.UUID,
    body: ModuleCreate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_track(db, track_id, require_org_scope(user))
    title = await ensure_unique_module_title(db, track_id, body.title)
    module = Module(track_id=track_id, **{**body.model_dump(), "title": title})
    db.add(module)
    await db.flush()
    await db.refresh(module, ["lessons"])
    return module


@router.patch("/modules/{module_id}", response_model=ModuleOut,
              dependencies=[Depends(can_edit)])
async def update_module(
    module_id: uuid.UUID,
    body: ModuleUpdate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    module = await _get_module(db, module_id, require_org_scope(user))
    data = body.model_dump(exclude_unset=True)
    if "title" in data:
        data["title"] = await ensure_unique_module_title(
            db, module.track_id, data["title"], exclude_module_id=module_id
        )
    for key, value in data.items():
        setattr(module, key, value)
    await db.flush()
    await db.refresh(module, ["lessons"])
    return module


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(can_edit)])
async def delete_module(
    module_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    module = await _get_module(db, module_id, require_org_scope(user))
    storage = get_storage()
    if module.description_source_storage_key:
        await storage.delete(module.description_source_storage_key)
    for lesson in module.lessons:
        if lesson.content_source_storage_key:
            await storage.delete(lesson.content_source_storage_key)
    await db.execute(
        delete(CohortModuleProfessor).where(CohortModuleProfessor.module_id == module_id)
    )
    await db.delete(module)


@router.post("/modules/{module_id}/lessons", response_model=LessonOut,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(can_edit)])
async def create_lesson(
    module_id: uuid.UUID,
    body: LessonCreate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_module(db, module_id, require_org_scope(user))
    title = await ensure_unique_lesson_title(db, module_id, body.title)
    lesson = Lesson(module_id=module_id, **{**body.model_dump(), "title": title})
    db.add(lesson)
    await db.flush()
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=LessonOut,
              dependencies=[Depends(can_edit)])
async def update_lesson(
    lesson_id: uuid.UUID,
    body: LessonUpdate,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await _get_lesson(db, lesson_id, require_org_scope(user))
    data = body.model_dump(exclude_unset=True)
    if "title" in data:
        data["title"] = await ensure_unique_lesson_title(
            db, lesson.module_id, data["title"], exclude_lesson_id=lesson_id
        )
    for key, value in data.items():
        setattr(lesson, key, value)
    await db.flush()
    return lesson


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(can_edit)])
async def delete_lesson(
    lesson_id: uuid.UUID,
    user: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await _get_lesson(db, lesson_id, require_org_scope(user))
    if lesson.content_source_storage_key:
        await get_storage().delete(lesson.content_source_storage_key)
    await db.delete(lesson)
