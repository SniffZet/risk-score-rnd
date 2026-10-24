"""Аналитика: сводка и график оттока."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.deps import CurrentUser, Repo
from backend.domain import Summary
from backend.schemas import ChurnChartPoint, SummaryOut
from backend.state import state

router = APIRouter()


def _to_summary(summary: Summary) -> SummaryOut:
    return SummaryOut(
        referenceTime=summary.referenceTime,
        horizonDays=summary.horizonDays,
        customersTotal=summary.customersTotal,
        customersByLevel=summary.customersByLevel,
        expectedLossTotal=summary.expectedLossTotal,
        expectedLossByLevel=summary.expectedLossByLevel,
        revenueTotal=summary.revenueTotal,
        servicesAtRisk=summary.servicesAtRisk,
    )


@router.get("/summary", response_model=SummaryOut, summary="Сводка по рискам")
async def summary(repository: Repo, _: CurrentUser) -> SummaryOut:
    # Источник правды — хранилище; state используется как быстрый кэш, но
    # после рестарта он пуст, поэтому читаем из хранилища.
    stored = await repository.get_summary()
    if stored is None:
        if state.summary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Данные ещё не рассчитаны",
            )
        stored = state.summary
    return _to_summary(stored)


@router.get("/churn-chart", response_model=list[ChurnChartPoint], summary="График оттока по дням")
async def churn_chart(repository: Repo, _: CurrentUser) -> list[ChurnChartPoint]:
    # Агрегация по дням делается в хранилище (в SQL — GROUP BY), поэтому
    # эндпоинт не зависит от общего числа услуг.
    settings = await repository.get_model_settings()
    buckets = await repository.churn_buckets(settings["prolongWaitGraceDays"])
    return [
        ChurnChartPoint(
            date=day,
            deleted_actual=values.get("deleted", 0),
            expected_nonrenewals=values.get("expected", 0),
        )
        for day, values in sorted(buckets.items())
    ]
