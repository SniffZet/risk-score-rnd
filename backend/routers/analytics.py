from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.deps import CurrentUser, Repo
from backend.routers.convert import to_chart, to_summary, to_transition
from backend.schemas import ChurnChartOut, SummaryOut, TransitionOut
from backend.state import state

router = APIRouter()


@router.get("/summary", response_model=SummaryOut, summary="Сводка по рискам")
async def summary(repository: Repo, _: CurrentUser) -> SummaryOut:
    stored = await repository.get_summary()
    if stored is None:
        if state.summary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Данные ещё не рассчитаны",
            )
        stored = state.summary
    return to_summary(stored)


@router.get("/churn-chart", response_model=ChurnChartOut, summary="График оттока: факт и прогноз")
async def churn_chart(repository: Repo, _: CurrentUser) -> ChurnChartOut:
    chart = await repository.get_chart() or state.chart
    if chart is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Данные ещё не рассчитаны",
        )
    return to_chart(chart)


@router.get("/journal", response_model=list[TransitionOut], summary="Журнал переходов статусов")
async def journal(
    repository: Repo,
    _: CurrentUser,
    account_id: int | None = Query(None, description="только услуги этого клиента"),
    service_id: int | None = Query(None, description="только эта услуга"),
    limit: int = Query(100, ge=1, le=1000),
) -> list[TransitionOut]:
    events = await repository.list_journal(account_id=account_id, service_id=service_id, limit=limit)
    return [to_transition(e) for e in events]
