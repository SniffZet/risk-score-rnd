from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.config import settings
from backend.deps import CurrentUser, Repo
from backend.domain import Snapshot, utcnow
from backend.repository import Repository
from backend.routers.convert import to_summary
from backend.schemas import SnapshotIn, SnapshotOut, SnapshotPatchIn
from backend.services.ingest import merge_snapshot
from backend.services.journal import diff_snapshots
from backend.services.normalize import SnapshotError, parse_snapshot
from backend.services.recompute import recompute

router = APIRouter()


async def _apply(repository: Repository, snapshot: Snapshot, applied: dict[str, int], reason: str) -> SnapshotOut:
    current = await repository.get_snapshot()
    events = diff_snapshots(current, snapshot, utcnow()) if current.accounts else []

    await repository.replace_snapshot(snapshot)
    await repository.append_journal(events)
    summary = await recompute(repository, reason=reason)

    return SnapshotOut(
        counts={
            "accounts": len(snapshot.accounts),
            "services": len(snapshot.services),
            "transactions": len(snapshot.transactions),
        },
        applied=applied,
        transitions=len(events),
        summary=to_summary(summary),
    )


async def _replace_and_recompute(repository: Repository, raw: object) -> SnapshotOut:
    try:
        snapshot = parse_snapshot(raw)
    except SnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    applied = {
        "accounts": len(snapshot.accounts),
        "services": len(snapshot.services),
        "transactions": len(snapshot.transactions),
    }
    return await _apply(repository, snapshot, applied, reason="snapshot")


@router.get("/snapshot", response_model=Snapshot, summary="Текущие данные (формат models.Snapshot)")
async def get_snapshot(repository: Repo, _: CurrentUser) -> Snapshot:
    return await repository.get_snapshot()


@router.put("/snapshot", response_model=SnapshotOut, summary="Заменить данные (JSON в теле)")
async def put_snapshot(payload: SnapshotIn, repository: Repo, _: CurrentUser) -> SnapshotOut:
    return await _replace_and_recompute(repository, payload.model_dump())


@router.patch("/snapshot", response_model=SnapshotOut, summary="Догрузить изменения (upsert по id)")
async def patch_snapshot(payload: SnapshotPatchIn, repository: Repo, _: CurrentUser) -> SnapshotOut:
    current = await repository.get_snapshot()
    try:
        merged, applied = merge_snapshot(current, payload.model_dump())
    except SnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return await _apply(repository, merged, applied, reason="upsert")


@router.put("/snapshot/file", response_model=SnapshotOut, summary="Заменить данные (.json файлом)")
async def put_snapshot_file(
    repository: Repo,
    _: CurrentUser,
    file: UploadFile = File(..., description=".json в формате data.json"),
) -> SnapshotOut:
    filename = (file.filename or "").lower()
    if not filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ожидается файл с расширением .json",
        )

    limit = settings.MAX_UPLOAD_BYTES
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"файл больше {limit // (1024 * 1024)} МБ",
        )
    if not raw.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="файл пустой"
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"некорректный JSON: {exc.msg} (позиция {exc.pos})",
        ) from exc

    return await _replace_and_recompute(repository, parsed)
