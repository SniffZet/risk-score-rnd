"""Клиенты: список с фильтрами/сортировкой/пагинацией и детальная карточка."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.deps import CurrentUser, Repo
from backend.domain import CustomerRisk, Reason, ServiceRisk
from backend.schemas import (
    CustomerDetail,
    CustomerListItem,
    CustomersPage,
    ReasonOut,
    RiskLevel,
    ServiceRiskOut,
    SortField,
    SortOrder,
)

router = APIRouter()


def _to_reason(reason: Reason) -> ReasonOut:
    return ReasonOut(
        feature=reason.feature,
        title=reason.title,
        serviceId=reason.serviceId,
        strength=reason.strength,
        weight=reason.weight,
        impact=reason.impact,
        text=reason.text,
    )


def _to_service_risk(service: ServiceRisk) -> ServiceRiskOut:
    return ServiceRiskOut(
        serviceId=service.serviceId,
        name=service.name,
        status=service.status.value,
        paymentTerm=service.paymentTerm.value,
        price=service.price,
        expiresAt=service.expiresAt,
        autoProlong=service.autoProlong,
        risk=service.risk,
        revenue=service.revenue,
        expectedLoss=service.expectedLoss,
        reasons=[_to_reason(r) for r in service.reasons],
    )


def _to_list_item(customer: CustomerRisk) -> CustomerListItem:
    return CustomerListItem(
        accountId=customer.accountId,
        email=customer.email,
        balance=customer.balance,
        totalReplenished=customer.totalReplenished,
        availableFunds=customer.availableFunds,
        score=customer.score,
        level=customer.level,
        loyalty=customer.loyalty,
        expectedLoss=customer.expectedLoss,
        revenue=customer.revenue,
    )


@router.get("", response_model=CustomersPage, summary="Список клиентов")
async def list_customers(
    repository: Repo,
    _: CurrentUser,
    sort_by: SortField = Query("accountId", description="поле сортировки"),
    sort_order: SortOrder = Query("asc", description="направление сортировки"),
    level: RiskLevel | None = Query(None, description="фильтр по уровню риска"),
    search: str | None = Query(None, max_length=256, description="поиск по email"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CustomersPage:
    # Фильтрация, сортировка и пагинация выполняются в хранилище.
    # В SQL-реализации это WHERE / ORDER BY / LIMIT — без выгрузки всей таблицы.
    customers, total = await repository.list_customers(
        search=search,
        level=level,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return CustomersPage(
        items=[_to_list_item(c) for c in customers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{account_id}", response_model=CustomerDetail, summary="Карточка клиента")
async def get_customer(account_id: int, repository: Repo, _: CurrentUser) -> CustomerDetail:
    customer = await repository.get_customer(account_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Клиент не найден или данные ещё не рассчитаны",
        )

    base = _to_list_item(customer)
    return CustomerDetail(
        **base.model_dump(),
        reasons=[_to_reason(r) for r in customer.reasons],
        services=[_to_service_risk(s) for s in customer.services],
    )
