from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict

from backend.domain import ChurnChart, CustomerRisk, Summary, evaluate, summarize, timeline
from backend.repository import Repository
from backend.services import sse
from backend.services.metrics import refresh_metrics
from backend.state import state

logger = logging.getLogger(__name__)


def run_model(snapshot, settings: dict, observed: dict) -> tuple[list[CustomerRisk], Summary, ChurnChart]:
    customers = evaluate(snapshot, settings)
    summary = summarize(customers, snapshot, settings)
    chart = timeline(customers, snapshot, settings, observed)
    return customers, summary, chart


def _fingerprint(summary: Summary) -> str:
    raw = json.dumps(asdict(summary), default=str, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def recompute(
    repository: Repository,
    *,
    settings: dict | None = None,
    persist_settings: bool = False,
    reason: str = "manual",
) -> Summary:
    snapshot = await repository.get_snapshot()
    if settings is None:
        settings = await repository.get_model_settings()
    observed = await repository.observed_deletions()

    customers, summary, chart = await asyncio.to_thread(run_model, snapshot, settings, observed)

    if persist_settings:
        await repository.save_model_settings(settings)
    await repository.save_risk(customers, summary, chart)

    fingerprint = _fingerprint(summary)
    changed = fingerprint != state.fingerprint
    state.summary = summary
    state.chart = chart
    state.fingerprint = fingerprint
    state.last_updated = summary.referenceTime
    state.last_error = None
    state.recompute_count += 1

    refresh_metrics()
    if changed or reason != "timer":
        await sse.publish(
            "recalculated",
            {
                "at": summary.referenceTime.isoformat(),
                "reason": reason,
                "customers": summary.customersTotal,
                "expectedLossTotal": summary.expectedLossTotal,
            },
        )
    logger.debug(
        "Пересчёт (%s) завершён: клиентов %d, потери %d, услуг под риском %d, изменилось=%s",
        reason,
        summary.customersTotal,
        summary.expectedLossTotal,
        summary.servicesAtRisk,
        changed,
    )
    return summary


async def preview(repository: Repository, settings: dict) -> Summary:
    snapshot = await repository.get_snapshot()
    customers = await asyncio.to_thread(evaluate, snapshot, settings)
    return await asyncio.to_thread(summarize, customers, snapshot, settings)
