"""Настройки модели: чтение, частичное обновление, пересчёт.

Валидацию значений выполняет САМА модель — ``merge_settings`` из
``backend.risk.defaults``. Мы не дублируем правила: иначе появились бы две
расходящиеся правды о допустимых весах и порогах. Наша задача — превратить
``ValueError`` модели в понятный HTTP-422.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.deps import CurrentUser, Repo
from backend.domain import FEATURES, merge_settings
from backend.schemas import FeatureMeta, SettingsOut, SettingsPatch
from backend.services.recompute import recompute

router = APIRouter()


def _patch_payload(patch: SettingsPatch) -> dict:
    """Собрать словарь правок для модели.

    ``exclude_unset`` — чтобы не подставлять дефолты Pydantic вместо
    незаданных полей (иначе патч одного веса затирал бы остальные).

    ``None`` отбрасываем, кроме ``referenceTime``: только у него ``null``
    несёт смысл («брать время из данных»). Для остальных ключей ``null`` —
    невалидное значение, и передавать его в модель не нужно.
    """
    data = patch.model_dump(exclude_unset=True)
    return {
        key: value
        for key, value in data.items()
        if value is not None or key == "referenceTime"
    }


def _features_meta() -> list[FeatureMeta]:
    """Описание признаков для формы настроек — берём из самой модели."""
    return [
        FeatureMeta(
            code=uid,
            title=feature.name,
            description=feature.description,
            default_weight=feature.baseWeight,
        )
        for uid, feature in FEATURES.items()
    ]


def _to_out(settings: dict) -> SettingsOut:
    return SettingsOut(
        weights=settings["weights"],
        highThreshold=settings["highThreshold"],
        mediumThreshold=settings["mediumThreshold"],
        horizonDays=settings["horizonDays"],
        expiringWindowDays=settings["expiringWindowDays"],
        prolongWaitGraceDays=settings["prolongWaitGraceDays"],
        countWithdrawBalance=settings["countWithdrawBalance"],
        referenceTime=settings["referenceTime"],
        features=_features_meta(),
    )


@router.get("/settings", response_model=SettingsOut, summary="Текущие настройки модели")
async def get_settings(repository: Repo, _: CurrentUser) -> SettingsOut:
    return _to_out(await repository.get_model_settings())


@router.patch("/settings", response_model=SettingsOut, summary="Обновить настройки и пересчитать")
async def patch_settings(patch: SettingsPatch, repository: Repo, _: CurrentUser) -> SettingsOut:
    current = await repository.get_model_settings()
    patch_data = _patch_payload(patch)

    # Пустой патч — не повод гонять модель по всем клиентам.
    if not patch_data:
        return _to_out(current)

    try:
        # Порядок аргументов важен: base — текущее состояние, patch — правки.
        merged = merge_settings(patch=patch_data, base=current)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await repository.save_model_settings(merged)

    # Пересчёт синхронно: клиент получает ответ с уже новыми оценками.
    await recompute(repository)
    return _to_out(merged)
