from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.deps import CurrentUser, Repo
from backend.domain import FEATURES, merge_settings
from backend.routers.convert import to_summary
from backend.schemas import FeatureMeta, SettingsOut, SettingsPatch, SettingsPreviewOut
from backend.services.recompute import preview, recompute

router = APIRouter()


def _patch_payload(patch: SettingsPatch) -> dict:
    data = patch.model_dump(exclude_unset=True)
    return {
        key: value
        for key, value in data.items()
        if value is not None or key == "referenceTime"
    }


def _features_meta() -> list[FeatureMeta]:
    return [
        FeatureMeta(
            code=uid,
            title=feature.name,
            description=feature.description,
            default_weight=feature.baseWeight,
            kind=feature.kind,
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
        paymentLookbackDays=settings["paymentLookbackDays"],
        countWithdrawBalance=settings["countWithdrawBalance"],
        capRevenueByCapacity=settings["capRevenueByCapacity"],
        bigSpenderThreshold=settings["bigSpenderThreshold"],
        newCustomerDays=settings["newCustomerDays"],
        loyalTenureDays=settings["loyalTenureDays"],
        referenceTime=settings["referenceTime"],
        features=_features_meta(),
    )


async def _merged(patch: SettingsPatch, repository) -> tuple[dict, dict]:
    current = await repository.get_model_settings()
    patch_data = _patch_payload(patch)
    if not patch_data:
        return current, patch_data
    try:
        return merge_settings(patch=patch_data, base=current), patch_data
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/settings", response_model=SettingsOut, summary="Текущие настройки модели")
async def get_settings(repository: Repo, _: CurrentUser) -> SettingsOut:
    return _to_out(await repository.get_model_settings())


@router.patch("/settings", response_model=SettingsOut, summary="Обновить настройки и пересчитать")
async def patch_settings(patch: SettingsPatch, repository: Repo, _: CurrentUser) -> SettingsOut:
    merged, patch_data = await _merged(patch, repository)
    if not patch_data:
        return _to_out(merged)

    await recompute(repository, settings=merged, persist_settings=True, reason="settings")
    return _to_out(merged)


@router.post("/settings/preview", response_model=SettingsPreviewOut, summary="Что-если: сводка без сохранения")
async def preview_settings(patch: SettingsPatch, repository: Repo, _: CurrentUser) -> SettingsPreviewOut:
    merged, _patch_data = await _merged(patch, repository)
    summary = await preview(repository, merged)
    return SettingsPreviewOut(settings=_to_out(merged), summary=to_summary(summary))
