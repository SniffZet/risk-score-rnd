"""Первичная загрузка данных из data/data.json.

Загружаем только если хранилище пустое — повторный старт не должен затирать
данные, которые уже загрузили через API.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.repository import Repository
from backend.services.normalize import SnapshotError, parse_snapshot

logger = logging.getLogger(__name__)


async def seed_if_empty(repository: Repository, path: str | Path) -> bool:
    """Загрузить снапшот, если данных ещё нет.

    Возвращает True, если данные были загружены. Ошибки чтения не роняют
    приложение: без данных сервис поднимется и отдаст пустые списки, а данные
    можно будет загрузить через PUT /source/snapshot.
    """
    if not await repository.is_empty():
        logger.info("Данные уже загружены, первичная загрузка пропущена")
        return False

    file_path = Path(path)
    if not file_path.is_file():
        logger.warning("Файл первичных данных не найден: %s", file_path.resolve())
        return False

    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        snapshot = parse_snapshot(raw)
    except (OSError, SnapshotError, json.JSONDecodeError) as exc:
        logger.error("Не удалось загрузить %s: %s", file_path, exc)
        return False

    await repository.replace_snapshot(snapshot)
    logger.info(
        "Загружены данные: аккаунтов %d, услуг %d, транзакций %d",
        len(snapshot.accounts),
        len(snapshot.services),
        len(snapshot.transactions),
    )
    return True
