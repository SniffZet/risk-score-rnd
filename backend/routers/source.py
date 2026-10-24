"""Загрузка снапшота данных: телом JSON или файлом.

Формат — ``data.json``: ``{"accounts": [...], "services": [...],
"transactions": [...]}``. Проверка выполняется в ``services.normalize`` по
ограничениям SQL-схемы.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.config import settings
from backend.deps import CurrentUser, Repo
from backend.repository import Repository
from backend.schemas import SnapshotIn, SnapshotOut, SummaryOut
from backend.services.normalize import SnapshotError, parse_snapshot
from backend.services.recompute import recompute

router = APIRouter()


async def _replace_and_recompute(repository: Repository, raw: object) -> SnapshotOut:
    try:
        snapshot = parse_snapshot(raw)
    except SnapshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    await repository.replace_snapshot(snapshot)
    summary = await recompute(repository)

    return SnapshotOut(
        counts={
            "accounts": len(snapshot.accounts),
            "services": len(snapshot.services),
            "transactions": len(snapshot.transactions),
        },
        summary=SummaryOut(
            referenceTime=summary.referenceTime,
            horizonDays=summary.horizonDays,
            customersTotal=summary.customersTotal,
            customersByLevel=summary.customersByLevel,
            expectedLossTotal=summary.expectedLossTotal,
            expectedLossByLevel=summary.expectedLossByLevel,
            revenueTotal=summary.revenueTotal,
            servicesAtRisk=summary.servicesAtRisk,
        ),
    )


@router.put("/snapshot", response_model=SnapshotOut, summary="Заменить данные (JSON в теле)")
async def put_snapshot(payload: SnapshotIn, repository: Repo, _: CurrentUser) -> SnapshotOut:
    return await _replace_and_recompute(repository, payload.model_dump())


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

    # Читаем не больше лимита + 1 байт: так мы узнаём о превышении, не
    # выгружая гигабайты в память.
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
