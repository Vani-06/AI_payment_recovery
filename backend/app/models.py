"""ORM table models — Phase 1.

Storage shapes only. Wire shapes live in ``schemas.py``; the API layer (Phase 3) maps
between them. Enum-valued columns are stored as plain strings (``.value``) so adding a
cause or action later is a code change, not a DB migration.

Money is a whole-INR ``int`` everywhere. Timestamps are ISO-8601 UTC strings.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    __tablename__ = "customer"

    id: str = Field(primary_key=True)  # cus_0001
    label: str  # "Customer #1" — the only identity the model / audit ever see
    name: str  # real name — UI-local, never sent to the model or written to audit
    segment: str  # b2c | b2b
    region: str  # south | west | north | east
    method_pref: str  # upi | card | netbanking | wallet
    dnd: bool = False
    opt_out: bool = False
    contact_count_7d: int = 0
    last_contacted_at: str | None = None
    promise_to_pay_date: str | None = None
    on_hold: bool = False
    responsiveness: float  # 0..1, HIDDEN — outcome engine only, never serialized


class RevenueEvent(SQLModel, table=True):
    __tablename__ = "revenue_event"

    id: str = Field(primary_key=True)  # evt_00001
    type: str  # EventType
    customer_id: str = Field(foreign_key="customer.id", index=True)
    amount: int  # INR at risk
    currency: str = "INR"
    created_at: str
    gateway: str
    method: str
    issuer: str
    bin: str | None = None
    status: str
    true_cause: str  # HIDDEN ground truth — never serialized to the wire
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
