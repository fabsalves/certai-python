import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.cohort import CohortModuleProfessor
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
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

can_edit = require_roles(Role.DESIGNER, Role.ADMIN)


async def _get_track(db: AsyncSession, track_id: uuid.UUID) -> Track:
    stmt = (
        select(Track)
        .where(Track.id == track_id)
        .options(selectinload(Track.modules).selectinload(Module.lessons))
    )
    track = (await db.execute(stmt)).scalar_one_or_none()
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trilha não encontrada")
    return track


@router.get("", response_model=list[TrackOut], dependencies=[Depends(can_edit)])
async def list_tracks(_: Annotated[User, Depends(can_edit)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(Track).options(
        selectinload(Track.modules).selectinload(Module.lessons)
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/{track_id}", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def get_track(
    track_id: uuid.UUID,
    _: Annotated[User, Depends(can_edit)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await _get_track(db, track_id)


@router.post("", response_model=TrackOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(can_edit)])
async def create_track(body: TrackCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    track = Track(**body.model_dump())
    db.add(track)
    await db.flush()
    await db.refresh(track, ["modules"])
    return track


@router.patch("/{track_id}", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def update_track(
    track_id: uuid.UUID,
    body: TrackUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False:
        data["published"] = False
    for key, value in data.items():
        setattr(track, key, value)
    await db.flush()
    return await _get_track(db, track_id)


@router.post("/{track_id}/publish", response_model=TrackOut,
             dependencies=[Depends(can_edit)])
async def publish_track(
    track_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    track = await _get_track(db, track_id)
    track.published = True
    await db.flush()
    return await _get_track(db, track_id)


@router.post("/{track_id}/material", response_model=TrackOut, dependencies=[Depends(can_edit)])
async def upload_track_material(
    track_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(description="PDF ou PPT da trilha")],
):
    """Attach or replace the single material file for a track (PDF/PPT/PPTX)."""
    track = await _get_track(db, track_id)
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
    await db.flush()
    return await _get_track(db, track_id)


@router.get("/{track_id}/material", dependencies=[Depends(can_edit)])
async def download_track_material(
    track_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id)
    return await file_response(
        storage_key=track.material_storage_key,
        filename=track.material_filename or "material",
        content_type=track.material_content_type,
    )


@router.post("/{track_id}/modules", response_model=ModuleOut,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(can_edit)])
async def create_module(
    track_id: uuid.UUID, body: ModuleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    if await db.get(Track, track_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trilha não encontrada")
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    module = await db.get(Module, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo não encontrado")
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
    module_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    module = await db.get(Module, module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo não encontrado")
    await db.execute(
        delete(CohortModuleProfessor).where(CohortModuleProfessor.module_id == module_id)
    )
    await db.delete(module)


@router.post("/modules/{module_id}/lessons", response_model=LessonOut,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(can_edit)])
async def create_lesson(
    module_id: uuid.UUID, body: LessonCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    if await db.get(Module, module_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo não encontrado")
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")
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
    lesson_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")
    await db.delete(lesson)
