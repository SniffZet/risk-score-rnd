"""Пересчёт рисков: хранилище → модель → хранилище + состояние.

Единственное место, где бэкенд вызывает модель. Модель берёт «сейчас» из
настроек или из самих данных (``Snapshot.latest_event``), поэтому здесь мы
не подставляем системное время.

Исключения не глотаются: их обрабатывает вызывающий (фоновая задача или
роутер).
"""
from __future__ import annotations

import logging

from backend.domain import CustomerRisk, Summary, evaluate, summarize
from backend.repository import Repository
from backend.services import sse
from backend.services.metrics import refresh_metrics
from backend.state import state

logger = logging.getLogger(__name__)


async def recompute(repository: Repository) -> Summary:
    """Прогнать модель по текущим данным и сохранить результат."""
    snapshot = await repository.get_snapshot()
    settings = await repository.get_model_settings()

    customers: list[CustomerRisk] = evaluate(snapshot, settings)
    summary: Summary = summarize(customers, snapshot, settings)

    await repository.save_risk(customers, summary)

    state.summary = summary
    state.last_updated = summary.referenceTime
    state.last_error = None
    state.recompute_count += 1

    refresh_metrics()
    await sse.publish(
        "recalculated",
        {
            "at": summary.referenceTime.isoformat(),
            "customers": summary.customersTotal,
            "expectedLossTotal": summary.expectedLossTotal,
        },
    )
    logger.debug(
        "Пересчёт завершён: клиентов %d, потери %d, услуг под риском %d",
        summary.customersTotal,
        summary.expectedLossTotal,
        summary.servicesAtRisk,
    )
    return summary
