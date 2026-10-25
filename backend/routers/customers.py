from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.deps import CurrentUser, Repo
from backend.domain import RISK_LEVELS
from backend.routers.convert import to_list_item, to_reason, to_service_risk, to_transition
from backend.schemas import (
    CustomerDetail,
    CustomersPage,
    SortField,
    SortOrder,
)

router = APIRouter()

EXPORT_LIMIT = 100_000
HISTORY_LIMIT = 50

LEVEL_DESCRIPTION = "уровень риска; несколько через запятую, например high,medium — «зона риска»"


def _levels(level: str | None) -> list[str] | None:
    if not level:
        return None
    values = [v.strip() for v in level.split(",") if v.strip()]
    unknown = [v for v in values if v not in RISK_LEVELS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"неизвестный уровень риска: {', '.join(unknown)}; допустимо: {', '.join(RISK_LEVELS)}",
        )
    return values or None


@router.get("", response_model=CustomersPage, summary="Список клиентов")
async def list_customers(
    repository: Repo,
    _: CurrentUser,
    sort_by: SortField = Query("accountId", description="поле сортировки"),
    sort_order: SortOrder = Query("asc", description="направление сортировки"),
    level: str | None = Query(None, max_length=64, description=LEVEL_DESCRIPTION),
    search: str | None = Query(None, max_length=256, description="поиск по email"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CustomersPage:
    customers, total = await repository.list_customers(
        search=search,
        levels=_levels(level),
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return CustomersPage(
        items=[to_list_item(c) for c in customers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/export.csv",
    summary="Выгрузка клиентов в CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV с разделителем «;» и BOM для Excel"}},
)
async def export_csv(
    repository: Repo,
    _: CurrentUser,
    sort_by: SortField = Query("score"),
    sort_order: SortOrder = Query("desc"),
    level: str | None = Query(None, max_length=64, description=LEVEL_DESCRIPTION),
    search: str | None = Query(None, max_length=256),
) -> Response:
    customers, _total = await repository.list_customers(
        search=search, levels=_levels(level), sort_by=sort_by, sort_order=sort_order, limit=EXPORT_LIMIT, offset=0
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "id", "email", "balance_eur", "total_replenished_eur", "available_funds_eur",
        "score", "level", "loyalty", "expected_loss_eur", "revenue_eur", "action", "main_reason",
    ])
    for c in customers:
        writer.writerow([
            c.accountId,
            c.email,
            f"{c.balance / 100:.2f}",
            f"{c.totalReplenished / 100:.2f}",
            f"{c.availableFunds / 100:.2f}",
            "" if c.score is None else c.score,
            c.level,
            "" if c.loyalty is None else c.loyalty,
            f"{c.expectedLoss / 100:.2f}",
            f"{c.revenue / 100:.2f}",
            c.action.title if c.action else "",
            c.reasons[0].text if c.reasons else "",
        ])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="customers-at-risk.csv"'},
    )


@router.get("/{account_id}", response_model=CustomerDetail, summary="Карточка клиента")
async def get_customer(account_id: int, repository: Repo, _: CurrentUser) -> CustomerDetail:
    customer = await repository.get_customer(account_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Клиент не найден или данные ещё не рассчитаны",
        )

    base = to_list_item(customer, reasons_limit=None)
    history = await repository.list_journal(account_id=account_id, limit=HISTORY_LIMIT)
    return CustomerDetail(
        **base.model_dump(exclude={"reasons"}),
        account=await repository.get_account(account_id),
        reasons=[to_reason(r) for r in customer.reasons],
        services=[to_service_risk(s) for s in customer.services],
        history=[to_transition(e) for e in history],
    )
