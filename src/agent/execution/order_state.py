"""Order lifecycle states for future live broker adapters (paper fills stay sync)."""

from __future__ import annotations

from enum import Enum


class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELED = "CANCELED"
    CANCELLED = "CANCELED"  # alias spelling
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


# Paper adapter may jump CREATED -> FILLED deterministically.
# Live adapters must not treat submit_order() as fill.
# SimulatedBroker exercises the full machine for readiness tests.
