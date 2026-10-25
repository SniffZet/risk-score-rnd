from __future__ import annotations

import time

from prometheus_client import Gauge

from backend.domain import FEATURES, RISK_LEVELS, PaymentTerm
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
    "Выручка в горизонте прогноза с учётом платёжеспособности, в еврокопейках",
)
revenue_full_total = Gauge(
    "churn_revenue_full_cents",
    "Выручка в горизонте прогноза без ограничения платёжеспособностью, в еврокопейках",
)
expected_loss_by_term = Gauge(
    "churn_expected_loss_by_term_cents",
    "Ожидаемые потери по периоду оплаты услуги, в еврокопейках",
    ["term"],
)
feature_customers = Gauge(
    "churn_feature_customers_total",
    "У скольких клиентов сработал признак",
    ["feature"],
)
feature_loss = Gauge(
    "churn_feature_expected_loss_cents",
    "Ожидаемые потери, отнесённые к признаку, в еврокопейках",
    ["feature"],
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
    "Опорное время последнего расчёта (unix time): для тестовых данных это дата в данных, а не сейчас",
)
last_recompute_wallclock = Gauge(
    "churn_last_recompute_wallclock_seconds",
    "Когда пересчёт выполнялся в последний раз по часам сервера (unix time): для алерта о застое",
)

for _level in RISK_LEVELS:
    customers_by_level.labels(level=_level).set(0)
    expected_loss_by_level.labels(level=_level).set(0)
for _term in PaymentTerm:
    expected_loss_by_term.labels(term=_term.value).set(0)
for _feature in FEATURES:
    feature_customers.labels(feature=_feature).set(0)
    feature_loss.labels(feature=_feature).set(0)


def refresh_metrics() -> None:
    summary = state.summary
    if summary is None:
        return

    for level in RISK_LEVELS:
        customers_by_level.labels(level=level).set(summary.customersByLevel.get(level, 0))
        expected_loss_by_level.labels(level=level).set(summary.expectedLossByLevel.get(level, 0))
    for term in PaymentTerm:
        expected_loss_by_term.labels(term=term.value).set(summary.expectedLossByTerm.get(term.value, 0))
    for impact in summary.features:
        feature_customers.labels(feature=impact.feature).set(impact.customers)
        feature_loss.labels(feature=impact.feature).set(impact.expectedLoss)

    expected_loss_total.set(summary.expectedLossTotal)
    revenue_total.set(summary.revenueTotal)
    revenue_full_total.set(summary.revenueFullTotal)
    services_at_risk.set(summary.servicesAtRisk)
    customers_total.set(summary.customersTotal)
    horizon_days.set(summary.horizonDays)
    last_recompute.set(summary.referenceTime.timestamp())
    last_recompute_wallclock.set(time.time())
