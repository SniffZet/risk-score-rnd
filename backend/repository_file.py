from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from backend.domain import (
    DEFAULT_SETTINGS,
    FEATURES,
    Session,
    Snapshot,
    Transition,
    merge_settings,
    parsetime,
    utcnow,
)
from backend.repository import MemoryRepository

logger = logging.getLogger(__name__)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"не сериализуется в JSON: {type(value).__name__}")


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class FileRepository(MemoryRepository):
    def __init__(self, data_dir: str | Path, journal_limit: int = 50_000) -> None:
        super().__init__(journal_limit=journal_limit)
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._settings_path = self._dir / "model_settings.json"
        self._snapshot_path = self._dir / "snapshot.json"
        self._journal_path = self._dir / "journal.json"
        self._sessions_path = self._dir / "sessions.json"
        self._load()

    def _load(self) -> None:
        if self._settings_path.is_file():
            try:
                saved = _read_json(self._settings_path)
                saved = {k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}
                saved["weights"] = {k: v for k, v in saved.get("weights", {}).items() if k in FEATURES}
                self._model_settings = merge_settings(base=saved)
                logger.info("Настройки модели восстановлены из %s", self._settings_path)
            except (OSError, ValueError, TypeError) as exc:
                logger.error("Сохранённые настройки не прочитаны, беру по умолчанию: %s", exc)

        if self._snapshot_path.is_file():
            try:
                snapshot = Snapshot.format_dict(_read_json(self._snapshot_path))
                self._snapshot = snapshot
                self._accounts_by_id = {a.id: a for a in snapshot.accounts}
                logger.info("Снимок данных восстановлен из %s", self._snapshot_path)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logger.error("Сохранённый снимок не прочитан, будет первичная загрузка: %s", exc)

        if self._journal_path.is_file():
            try:
                events = [
                    Transition(
                        at=parsetime(e["at"]),
                        serviceId=int(e["serviceId"]),
                        ownerId=int(e["ownerId"]),
                        serviceName=str(e["serviceName"]),
                        field=str(e["field"]),
                        old=e.get("old"),
                        new=str(e["new"]),
                    )
                    for e in _read_json(self._journal_path)
                ]
                self._journal = events[-self._journal_limit :]
                logger.info("Журнал восстановлен: %d событий", len(self._journal))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logger.error("Журнал не прочитан, начинаю с пустого: %s", exc)

        if self._sessions_path.is_file():
            try:
                now = utcnow()
                for raw in _read_json(self._sessions_path):
                    session = Session(
                        id=str(raw["id"]),
                        user_id=int(raw["user_id"]),
                        created_at=parsetime(raw["created_at"]),
                        expires_at=parsetime(raw["expires_at"]),
                    )
                    if not session.is_expired(now):
                        self._sessions[session.id] = session
                logger.info("Сессии восстановлены: %d", len(self._sessions))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logger.error("Сессии не прочитаны, пользователи войдут заново: %s", exc)

    async def replace_snapshot(self, snapshot: Snapshot) -> None:
        await super().replace_snapshot(snapshot)
        _write_json(self._snapshot_path, asdict(snapshot))

    async def save_model_settings(self, settings: dict) -> None:
        await super().save_model_settings(settings)
        _write_json(self._settings_path, self._model_settings)

    async def append_journal(self, events: list[Transition]) -> None:
        if not events:
            return
        await super().append_journal(events)
        _write_json(self._journal_path, [asdict(e) for e in self._journal])

    async def create_session(self, session: Session) -> None:
        await super().create_session(session)
        self._write_sessions()

    async def delete_session(self, session_id: str) -> None:
        await super().delete_session(session_id)
        self._write_sessions()

    def _write_sessions(self) -> None:
        now = utcnow()
        alive = [asdict(s) for s in self._sessions.values() if not s.is_expired(now)]
        _write_json(self._sessions_path, alive)
