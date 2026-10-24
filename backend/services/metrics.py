"""Prometheus-метрики.

Имена метрик оставлены прежними (``churn_*``), чтобы не ломать уже
настроенные дашборды и алерты.
"""
from __future__ import annotations

from prometheus_client import Gauge

from backend.domain import RISK_LEVELS
from backend.state import state

customers_by_level = Gauge(
    "churn_customers_by_risk_total",
    "Количество клиентов по уровням риска",
    ["level"],
)
expected_loss_total = Gauge(
    "churn_potential_loss_cents",
    "Ожидаемые потери в еврокопейках",
)
expected_loss_by_level = Gauge(
    "churn_expected_loss_by_level_cents",
    "Ожидаемые потери по уровням риска, в еврокопейках",
    ["level"],
)
revenue_total = Gauge(
    "churn_revenue_at_risk_cents",
    "Выручка в горизонте прогноза, в еврокопейках",
)
services_at_risk = Gauge(
    "churn_services_at_risk_total",
    "Количество услуг под риском",
)
customers_total = Gauge(
    "churn_customers_total",
    "Всего клиентов в расчёте",
)
horizon_days = Gauge(
    "churn_horizon_days",
    "Горизонт прогноза в днях",
)
last_recompute = Gauge(
    "churn_last_recompute_timestamp_seconds",
    "Опорное время последнего расчёта (unix time)",
)

# Все уровни объявляем заранее, иначе после пересчёта в метриках остаются
# «залипшие» значения прошлых запусков.
for _level in RISK_LEVELS:
    customers_by_level.labels(level=_level).set(0)
    expected_loss_by_level.labels(level=_level).set(0)


def refresh_metrics() -> None:
    summary = state.summary
    if summary is None:
        return

    for level in RISK_LEVELS:
        customers_by_level.labels(level=level).set(summary.customersByLevel.get(level, 0))
        expected_loss_by_level.labels(level=level).set(summary.expectedLossByLevel.get(level, 0))

    expected_loss_total.set(summary.expectedLossTotal)
    revenue_total.set(summary.revenueTotal)
    services_at_risk.set(summary.servicesAtRisk)
    customers_total.set(summary.customersTotal)
    horizon_days.set(summary.horizonDays)
    last_recompute.set(summary.referenceTime.timestamp())
