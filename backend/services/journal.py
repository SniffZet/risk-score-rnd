from __future__ import annotations

from datetime import datetime

from backend.domain import Snapshot, Transition


def diff_snapshots(old: Snapshot, new: Snapshot, at: datetime) -> list[Transition]:
    before = {s.id: s for s in old.services}
    events: list[Transition] = []
    for service in new.services:
        prev = before.get(service.id)
        if prev is None:
            continue
        if prev.status != service.status:
            events.append(
                Transition(
                    at=at,
                    serviceId=service.id,
                    ownerId=service.ownerId,
                    serviceName=service.name,
                    field="status",
                    old=prev.status.value,
                    new=service.status.value,
                )
            )
        if prev.autoProlong != service.autoProlong:
            events.append(
                Transition(
                    at=at,
                    serviceId=service.id,
                    ownerId=service.ownerId,
                    serviceName=service.name,
                    field="autoProlong",
                    old="on" if prev.autoProlong else "off",
                    new="on" if service.autoProlong else "off",
                )
            )
    return events
