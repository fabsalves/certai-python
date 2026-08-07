import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.db_events import enqueue_after_commit
from app.core.deps import require_roles
from app.models.cohort import CohortModuleProfessor
from app.models.track import Lesson, Module, Track
from app.models.user import Role, User
from app.services.ingestion.lesson_content_import_service import (
    AUDIO_EXTENSIONS,
    append_imported_text,
    classify_source,
    import_lesson_text,
)
from app.services.storage import get_storage
from app.services.storage.download import file_response
from app.services.track_structure import ensure_unique_lesson_title, ensure_unique_module_title
from app.services.upload_validation import (
    ATTACHMENT_MAX_BYTES,
    AUDIO_MAX_BYTES,
    LESSON_IMPORT_DOC_BY_EXT,
    MATERIAL_MAX_BYTES,
    TRACK_MATERIAL_BY_EXT,
    is_allowed_report_audio,
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


@router.post(
    "/lessons/{lesson_id}/import-text",
    response_model=ImportTextOut,
    dependencies=[Depends(can_edit)],
)
async def import_text_for_lesson_content(
    lesson_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(can_edit)],
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
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")

    filename = source.filename or ""
    try:
        kind = classify_source(filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if kind == "audio":
        if not is_allowed_report_audio(source.content_type, filename):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")
        content_type = source.content_type or "audio/webm"
        ext = Path(filename).suffix.lower() or ".webm"
        content = await read_upload(
            source,
            max_bytes=AUDIO_MAX_BYTES,
            too_large_message="Áudio muito grande (máx. 25 MB)",
            empty_message="Áudio vazio",
        )
    else:
        content_type, ext = resolve_allowed_type(source, LESSON_IMPORT_DOC_BY_EXT)
        content = await read_upload(
            source,
            max_bytes=ATTACHMENT_MAX_BYTES,
            too_large_message="Arquivo muito grande (máx. 10 MB)",
            empty_message="Arquivo vazio",
        )

    try:
        extracted = await import_lesson_text(
            content=content, filename=filename or f"source{ext}"
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except Exception as exc:
        detail = (
            "Não foi possível transcrever o áudio. Tente novamente."
            if kind == "audio"
            else "Não foi possível extrair o texto do arquivo. Tente novamente."
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail) from exc

    if not extracted.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nenhum texto foi obtido. Verifique o áudio ou se o PDF tem texto selecionável.",
        )

    storage = get_storage()
    if lesson.content_source_storage_key:
        await storage.delete(lesson.content_source_storage_key)

    key = f"lessons/{lesson_id}/content-source/{uuid.uuid4()}{ext}"
    await storage.save(content, key, content_type=content_type)

    base = lesson.content if base_text is None else base_text
    text = append_imported_text(base, extracted)
    lesson.content = text
    lesson.content_source_storage_key = key
    lesson.content_source_filename = filename or f"source{ext}"
    lesson.content_source_content_type = content_type
    lesson.content_source_kind = kind
    await db.flush()

    return ImportTextOut(
        text=text,
        content_source_filename=lesson.content_source_filename,
        content_source_content_type=lesson.content_source_content_type,
        content_source_kind=lesson.content_source_kind,
    )


@router.get(
    "/lessons/{lesson_id}/content-source",
    dependencies=[Depends(can_edit)],
)
async def download_lesson_content_source(
    lesson_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aula não encontrada")
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
    """Attach or replace the single material file for a track (PDF/PPT/PPTX).
    The AI ingestion (macro track guide) runs asynchronously after commit."""
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
    # New file invalidates any previous ingestion.
    track.material_extracted_text = ""
    track.material_guide = ""
    track.material_ingestion_status = "pending"
    await db.flush()

    from app.workers.tasks import ingest_track_material

    enqueue_after_commit(db, ingest_track_material, str(track_id))
    return await _get_track(db, track_id)


@router.post(
    "/{track_id}/material/ingest",
    response_model=TrackOut,
    dependencies=[Depends(can_edit)],
)
async def reingest_track_material(
    track_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    """Re-enqueue the AI ingestion of the track material (legacy files or failures)."""
    track = await _get_track(db, track_id)
    if not track.material_storage_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A trilha não possui material anexado")

    track.material_ingestion_status = "pending"
    await db.flush()

    from app.workers.tasks import ingest_track_material

    enqueue_after_commit(db, ingest_track_material, str(track_id))
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


@router.post(
    "/{track_id}/import-description",
    response_model=ImportTextOut,
    dependencies=[Depends(can_edit)],
)
async def import_text_for_track_description(
    track_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(can_edit)],
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
    track = await _get_track(db, track_id)
    filename = source.filename or ""
    try:
        kind = classify_source(filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if kind == "audio":
        if not is_allowed_report_audio(source.content_type, filename):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser de áudio")
        content_type = source.content_type or "audio/webm"
        ext = Path(filename).suffix.lower() or ".webm"
        content = await read_upload(
            source,
            max_bytes=AUDIO_MAX_BYTES,
            too_large_message="Áudio muito grande (máx. 25 MB)",
            empty_message="Áudio vazio",
        )
    else:
        content_type, ext = resolve_allowed_type(source, LESSON_IMPORT_DOC_BY_EXT)
        content = await read_upload(
            source,
            max_bytes=ATTACHMENT_MAX_BYTES,
            too_large_message="Arquivo muito grande (máx. 10 MB)",
            empty_message="Arquivo vazio",
        )

    try:
        extracted = await import_lesson_text(
            content=content, filename=filename or f"source{ext}"
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except Exception as exc:
        detail = (
            "Não foi possível transcrever o áudio. Tente novamente."
            if kind == "audio"
            else "Não foi possível extrair o texto do arquivo. Tente novamente."
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail) from exc

    if not extracted.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nenhum texto foi obtido. Verifique o áudio ou se o PDF tem texto selecionável.",
        )

    storage = get_storage()
    if track.description_source_storage_key:
        await storage.delete(track.description_source_storage_key)

    key = f"tracks/{track_id}/description-source/{uuid.uuid4()}{ext}"
    await storage.save(content, key, content_type=content_type)

    base = track.description if base_text is None else base_text
    text = append_imported_text(base, extracted)
    track.description = text
    track.description_source_storage_key = key
    track.description_source_filename = filename or f"source{ext}"
    track.description_source_content_type = content_type
    track.description_source_kind = kind
    await db.flush()

    return ImportTextOut(
        text=text,
        content_source_filename=track.description_source_filename,
        content_source_content_type=track.description_source_content_type,
        content_source_kind=track.description_source_kind,
    )


@router.get(
    "/{track_id}/description-source",
    dependencies=[Depends(can_edit)],
)
async def download_track_description_source(
    track_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    track = await _get_track(db, track_id)
    if not track.description_source_storage_key:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Nenhum arquivo fonte na descrição desta trilha"
        )
    return await file_response(
        storage_key=track.description_source_storage_key,
        filename=track.description_source_filename or "source",
        content_type=track.description_source_content_type,
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
    if lesson.content_source_storage_key:
        await get_storage().delete(lesson.content_source_storage_key)
    await db.delete(lesson)
