"""Deterministic seed generator — Phase 1 (SPEC.md §4, §7).

``generate(seed)`` is pure (no DB) and returns ``(customers, events)``. ``write()`` resets
Postgres and bulk-inserts. Same seed => byte-identical batch, every run.

The failure population has planted structure so Phase 2 attribution finds real signal:
an ICICI issuer-downtime spike, a degraded gateway, a regional UPI-timeout cluster, a
card-expiry batch, a salary-cycle dip, latency / shipping-shock checkout drop-off, and
overdue B2B invoices.

CLI:
    python -m app.seed --seed 7            # reset + populate Postgres
    python -m app.seed --seed 7 --report   # also print the oracle-vs-baseline check
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta

from .enums import Cause, EventType
from .models import Customer, RevenueEvent

# --------------------------------------------------------------------------------------
# Fixed reference clock — events fall in the 7 days before this instant.
# --------------------------------------------------------------------------------------
REFERENCE_NOW = datetime(2026, 9, 4, 10, 0, 0, tzinfo=UTC)
WEEK_START = REFERENCE_NOW - timedelta(days=7)
INCIDENT_DAY = (REFERENCE_NOW - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
GWDEG_DAY = (REFERENCE_NOW - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)

N_CUSTOMERS = 180
N_EVENTS = 400

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna",
    "Ishaan", "Rohan", "Kabir", "Ananya", "Diya", "Aadhya", "Saanvi", "Pari", "Anika",
    "Navya", "Myra", "Sara", "Kiara", "Riya", "Meera",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Rao", "Gupta", "Mehta", "Patel", "Khan",
    "Bose", "Das", "Menon", "Pillai", "Chopra", "Kulkarni", "Joshi", "Shetty", "Bhat", "Sinha",
]

REGION_WEIGHTS = {"south": 0.42, "west": 0.24, "north": 0.20, "east": 0.14}
METHOD_WEIGHTS = {"upi": 0.55, "card": 0.28, "netbanking": 0.10, "wallet": 0.07}
GATEWAY_WEIGHTS = {"razorpay_pg_a": 0.60, "razorpay_pg_b": 0.28, "razorpay_pg_c": 0.12}
BANK_ISSUERS = ["ICICI", "HDFC", "SBI", "Axis", "Kotak"]
CARD_BINS = {"414720": "Visa", "453210": "Visa", "524368": "Mastercard", "552255": "Mastercard", "607469": "RuPay", "652789": "RuPay"}

DEFAULT_STATUS = {
    EventType.payment_failed.value: "failed",
    EventType.subscription_failed.value: "failed",
    EventType.checkout_abandoned.value: "abandoned",
    EventType.invoice_overdue.value: "overdue",
}

#: Bucket sizes — sum must be N_EVENTS. Tune in Phase 9.
SKEW = {
    "issuer_downtime": 55,
    "gateway_degradation_pf": 20,
    "gateway_degradation_sub": 10,
    "upi_timeout": 60,
    "card_expired_sub": 45,
    "salary_cycle": 35,
    "checkout_latency": 40,
    "price_shock_shipping": 45,
    "invoice_forgot": 34,
    "invoice_disputed": 6,
    "invoice_mandate": 8,
    "sub_mandate": 15,
    "pf_disputed": 2,
    "generic_pf": 12,
    "generic_checkout": 11,
    "generic_sub": 2,
}

GENERIC_PF_CAUSES = [Cause.upi_timeout, Cause.insufficient_funds_salary_cycle, Cause.card_expired]
GENERIC_CHECKOUT_CAUSES = [Cause.checkout_latency, Cause.price_shock_shipping, Cause.forgot_to_pay]
GENERIC_SUB_CAUSES = [Cause.card_expired, Cause.mandate_revoked]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _weighted(rng: random.Random, mapping: dict[str, float]) -> str:
    r = rng.random()
    acc = 0.0
    key = ""
    for key, w in mapping.items():
        acc += w
        if r < acc:
            return key
    return key


def _clampi(x: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(x)))


def _dt_in_week(rng: random.Random) -> datetime:
    return WEEK_START + timedelta(seconds=rng.randint(0, 7 * 86400))


def _issuer_incident_dt(rng: random.Random) -> datetime:
    # 18:00-19:30 IST == 12:30-14:00 UTC on the incident day
    return INCIDENT_DAY + timedelta(hours=12, minutes=30, seconds=rng.randint(0, 90 * 60))


def _gwdeg_incident_dt(rng: random.Random) -> datetime:
    return GWDEG_DAY + timedelta(hours=9, seconds=rng.randint(0, 3 * 3600))


def _salary_dt(rng: random.Random) -> datetime:
    return datetime(2026, 9, rng.choice([1, 2, 3]), tzinfo=UTC) + timedelta(seconds=rng.randint(0, 86400))


def _amt_pf(rng: random.Random) -> int:
    return _clampi(rng.lognormvariate(7.82, 0.7), 200, 15000)


def _amt_checkout(rng: random.Random) -> int:
    return int(rng.triangular(500, 8000, 2200))


def _amt_sub(rng: random.Random) -> int:
    return rng.choices([199, 499, 799, 1499], weights=[3, 4, 3, 2])[0]


def _amt_invoice(rng: random.Random) -> int:
    return int(round(rng.triangular(15000, 250000, 60000), -2))


# --------------------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------------------


def _make_customers(rng: random.Random) -> list[Customer]:
    customers: list[Customer] = []
    for i in range(1, N_CUSTOMERS + 1):
        contact = 0 if rng.random() < 0.8 else rng.randint(1, 2)
        last_contacted = None
        if contact:
            last_contacted = _iso(REFERENCE_NOW - timedelta(hours=rng.randint(6, 140)))
        customers.append(
            Customer(
                id=f"cus_{i:04d}",
                label=f"Customer #{i}",
                name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                segment="b2b" if rng.random() < 0.20 else "b2c",
                region=_weighted(rng, REGION_WEIGHTS),
                method_pref=_weighted(rng, METHOD_WEIGHTS),
                dnd=rng.random() < 0.05,
                opt_out=rng.random() < 0.04,
                contact_count_7d=contact,
                last_contacted_at=last_contacted,
                promise_to_pay_date=None,  # set below for some invoice customers
                on_hold=rng.random() < 0.02,
                responsiveness=round(rng.triangular(0.15, 0.9, 0.55), 3),
            )
        )
    return customers


def generate(seed: int) -> tuple[list[Customer], list[RevenueEvent]]:
    rng = random.Random(seed)
    customers = _make_customers(rng)
    south = [c for c in customers if c.region == "south"] or customers
    raw: list[dict] = []

    def pick(region: str | None = None, bias: float = 0.8) -> Customer:
        if region == "south" and rng.random() < bias:
            return rng.choice(south)
        return rng.choice(customers)

    def add(
        etype: EventType,
        cause: Cause,
        cust: Customer,
        amount: int,
        created: datetime,
        *,
        gateway: str | None = None,
        method: str | None = None,
        issuer: str | None = None,
        bin_: str | None = None,
        meta: dict | None = None,
    ) -> None:
        raw.append(
            {
                "type": etype.value,
                "true_cause": cause.value,
                "customer_id": cust.id,
                "amount": int(amount),
                "created_at": _iso(created),
                "gateway": gateway or _weighted(rng, GATEWAY_WEIGHTS),
                "method": method or _weighted(rng, METHOD_WEIGHTS),
                "issuer": issuer or rng.choice(BANK_ISSUERS),
                "bin": bin_,
                "status": DEFAULT_STATUS[etype.value],
                "meta": meta or {},
            }
        )

    # 1. ICICI issuer downtime spike -----------------------------------------------------
    for _ in range(SKEW["issuer_downtime"]):
        add(
            EventType.payment_failed, Cause.issuer_downtime, pick("south", 0.7),
            _amt_pf(rng), _issuer_incident_dt(rng),
            method=rng.choice(["upi", "card"]), issuer="ICICI",
            meta={"attempt_no": rng.randint(1, 3), "error_code": "issuer_unavailable"},
        )

    # 2. Gateway B degradation ---------------------------------------------------------
    for _ in range(SKEW["gateway_degradation_pf"]):
        add(
            EventType.payment_failed, Cause.gateway_degradation, pick(),
            _amt_pf(rng), _gwdeg_incident_dt(rng), gateway="razorpay_pg_b",
            meta={"attempt_no": rng.randint(1, 3), "error_code": "gateway_timeout"},
        )
    for _ in range(SKEW["gateway_degradation_sub"]):
        add(
            EventType.subscription_failed, Cause.gateway_degradation, pick(),
            _amt_sub(rng), _gwdeg_incident_dt(rng), gateway="razorpay_pg_b",
            method="card", meta={"error_code": "gateway_timeout"},
        )

    # 3. Regional UPI-timeout cluster (Android, south) --------------------------------
    for _ in range(SKEW["upi_timeout"]):
        add(
            EventType.payment_failed, Cause.upi_timeout, pick("south", 0.75),
            _amt_pf(rng), _dt_in_week(rng), method="upi", issuer=rng.choice(BANK_ISSUERS),
            meta={"device": "android", "attempt_no": rng.randint(1, 4), "error_code": "upi_response_timeout"},
        )

    # 4. Card-expiry batch (subscriptions) -------------------------------------------
    for _ in range(SKEW["card_expired_sub"]):
        b = rng.choice(list(CARD_BINS))
        add(
            EventType.subscription_failed, Cause.card_expired, pick(),
            _amt_sub(rng), _dt_in_week(rng), method="card", issuer=CARD_BINS[b], bin_=b,
            meta={"decline_code": "expired_card"},
        )

    # 5. Salary-cycle dip (first days of month) -------------------------------------
    for _ in range(SKEW["salary_cycle"]):
        add(
            EventType.payment_failed, Cause.insufficient_funds_salary_cycle, pick(),
            _amt_pf(rng), _salary_dt(rng), method=rng.choice(["upi", "netbanking"]),
            meta={"decline_code": "insufficient_funds", "attempt_no": rng.randint(1, 2)},
        )

    # 6. Checkout latency drop-off ------------------------------------------------
    for _ in range(SKEW["checkout_latency"]):
        add(
            EventType.checkout_abandoned, Cause.checkout_latency, pick(),
            _amt_checkout(rng), _dt_in_week(rng),
            meta={"latency_ms": rng.randint(1800, 4200), "shipping_fee": rng.randint(0, 60), "step": "payment"},
        )

    # 7. Price-shock (shipping) drop-off ---------------------------------------
    for _ in range(SKEW["price_shock_shipping"]):
        cart = rng.randint(700, 4000)
        add(
            EventType.checkout_abandoned, Cause.price_shock_shipping, pick(),
            cart, _dt_in_week(rng),
            meta={"latency_ms": rng.randint(200, 900), "shipping_fee": rng.randint(180, 600), "cart_value": cart, "step": "shipping"},
        )

    # 8. Overdue invoices (B2B, large) --------------------------------------
    b2b = [c for c in customers if c.segment == "b2b"] or customers
    p2p_pool = list(b2b)
    rng.shuffle(p2p_pool)
    p2p_set = set(c.id for c in p2p_pool[: max(1, len(p2p_pool) // 7)])
    for cause_key, cause, extra in (
        ("invoice_forgot", Cause.forgot_to_pay, {}),
        ("invoice_disputed", Cause.disputed, {"dispute_flag": True}),
        ("invoice_mandate", Cause.mandate_revoked, {"mandate_status": "revoked"}),
    ):
        for _ in range(SKEW[cause_key]):
            cust = rng.choice(b2b)
            created = REFERENCE_NOW - timedelta(days=rng.randint(15, 75))
            if cust.id in p2p_set and cust.promise_to_pay_date is None:
                cust.promise_to_pay_date = _iso(REFERENCE_NOW + timedelta(days=rng.randint(2, 10)))
            add(
                EventType.invoice_overdue, cause, cust, _amt_invoice(rng), created,
                method="netbanking", meta={"days_overdue": (REFERENCE_NOW - created).days, **extra},
            )

    # 9. Mandate revoked (subscriptions) ---------------------------------
    for _ in range(SKEW["sub_mandate"]):
        add(
            EventType.subscription_failed, Cause.mandate_revoked, pick(),
            _amt_sub(rng), _dt_in_week(rng), method="upi",
            meta={"mandate_status": "revoked"},
        )

    # 10. Diffuse remainder (no engineered tell-tales) --------------------
    for _ in range(SKEW["pf_disputed"]):
        add(EventType.payment_failed, Cause.disputed, pick(), _amt_pf(rng), _dt_in_week(rng),
            meta={"chargeback": True})
    for _ in range(SKEW["generic_pf"]):
        add(EventType.payment_failed, rng.choice(GENERIC_PF_CAUSES), pick(), _amt_pf(rng), _dt_in_week(rng),
            meta={"attempt_no": rng.randint(1, 3)})
    for _ in range(SKEW["generic_checkout"]):
        add(EventType.checkout_abandoned, rng.choice(GENERIC_CHECKOUT_CAUSES), pick(), _amt_checkout(rng), _dt_in_week(rng),
            meta={"latency_ms": rng.randint(300, 1400), "shipping_fee": rng.randint(0, 120)})
    for _ in range(SKEW["generic_sub"]):
        add(EventType.subscription_failed, rng.choice(GENERIC_SUB_CAUSES), pick(), _amt_sub(rng), _dt_in_week(rng),
            method="card")

    raw.sort(key=lambda e: (e["created_at"], e["customer_id"]))
    events = [RevenueEvent(id=f"evt_{i + 1:05d}", currency="INR", **payload) for i, payload in enumerate(raw)]
    return customers, events


# --------------------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------------------


def write(customers: list[Customer], events: list[RevenueEvent]) -> None:
    from sqlmodel import Session

    from .db import ENGINE, reset_db

    reset_db()
    # expire_on_commit=False so the caller can still read the in-memory instances after.
    with Session(ENGINE, expire_on_commit=False) as s:
        s.add_all(customers)
        s.add_all(events)
        s.commit()


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Seed the Revenue Sherlock database.")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--report", action="store_true", help="print the oracle-vs-baseline check")
    args = ap.parse_args()

    customers, events = generate(args.seed)
    write(customers, events)
    at_risk = sum(e.amount for e in events)
    print(f"seeded  seed={args.seed}  customers={len(customers)}  events={len(events)}  at_risk=Rs {at_risk:,}")

    if args.report:
        from .analysis import format_report, summarize

        print(format_report(summarize(args.seed)))


if __name__ == "__main__":
    _cli()
