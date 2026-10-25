from __future__ import annotations

from backend.domain import (
    Action,
    ChurnChart,
    CustomerRisk,
    FeatureImpact,
    Reason,
    ServiceRisk,
    Summary,
    Transition,
)
from backend.schemas import (
    ActionOut,
    ChurnChartOut,
    ChurnChartPoint,
    CustomerListItem,
    FeatureImpactOut,
    ReasonOut,
    ServiceRiskOut,
    SummaryOut,
    TransitionOut,
)

LIST_REASONS = 3


def to_reason(reason: Reason) -> ReasonOut:
    return ReasonOut(
        feature=reason.feature,
        title=reason.title,
        serviceId=reason.serviceId,
        strength=reason.strength,
        weight=reason.weight,
        impact=reason.impact,
        text=reason.text,
        kind=reason.kind,
    )


def to_action(action: Action | None) -> ActionOut | None:
    if action is None:
        return None
    return ActionOut(code=action.code, title=action.title, text=action.text)


def to_service_risk(service: ServiceRisk) -> ServiceRiskOut:
    return ServiceRiskOut(
        serviceId=service.serviceId,
        name=service.name,
        status=service.status,
        paymentTerm=service.paymentTerm,
        price=service.price,
        expiresAt=service.expiresAt,
        autoProlong=service.autoProlong,
        risk=service.risk,
        revenue=service.revenue,
        revenueFull=service.revenueFull,
        expectedLoss=service.expectedLoss,
        nextChargeAt=service.nextChargeAt,
        reasons=[to_reason(r) for r in service.reasons],
    )


def to_list_item(customer: CustomerRisk, reasons_limit: int | None = LIST_REASONS) -> CustomerListItem:
    reasons = customer.reasons if reasons_limit is None else customer.reasons[:reasons_limit]
    return CustomerListItem(
        accountId=customer.accountId,
        email=customer.email,
        balance=customer.balance,
        totalReplenished=customer.totalReplenished,
        availableFunds=customer.availableFunds,
        capacity=customer.capacity,
        score=customer.score,
        level=customer.level,
        loyalty=customer.loyalty,
        expectedLoss=customer.expectedLoss,
        revenue=customer.revenue,
        revenueFull=customer.revenueFull,
        action=to_action(customer.action),
        reasons=[to_reason(r) for r in reasons],
    )


def to_feature_impact(impact: FeatureImpact) -> FeatureImpactOut:
    return FeatureImpactOut(
        feature=impact.feature,
        title=impact.title,
        weight=impact.weight,
        customers=impact.customers,
        services=impact.services,
        expectedLoss=impact.expectedLoss,
        kind=impact.kind,
    )


def to_summary(summary: Summary) -> SummaryOut:
    return SummaryOut(
        referenceTime=summary.referenceTime,
        horizonDays=summary.horizonDays,
        customersTotal=summary.customersTotal,
        customersByLevel=summary.customersByLevel,
        expectedLossTotal=summary.expectedLossTotal,
        expectedLossByLevel=summary.expectedLossByLevel,
        revenueTotal=summary.revenueTotal,
        revenueFullTotal=summary.revenueFullTotal,
        servicesAtRisk=summary.servicesAtRisk,
        revenueByTerm=summary.revenueByTerm,
        expectedLossByTerm=summary.expectedLossByTerm,
        features=[to_feature_impact(f) for f in summary.features],
    )


def to_chart(chart: ChurnChart) -> ChurnChartOut:
    return ChurnChartOut(
        bucket=chart.bucket,
        referenceDate=chart.referenceDate,
        horizonDays=chart.horizonDays,
        points=[
            ChurnChartPoint(
                date=p.date,
                deleted=p.deleted,
                deletedObserved=p.deletedObserved,
                expectedNonrenewals=p.expectedNonrenewals,
                servicesAtRisk=p.servicesAtRisk,
            )
            for p in chart.points
        ],
    )


def to_transition(event: Transition) -> TransitionOut:
    return TransitionOut(
        at=event.at,
        serviceId=event.serviceId,
        ownerId=event.ownerId,
        serviceName=event.serviceName,
        field=event.field,
        old=event.old,
        new=event.new,
    )
