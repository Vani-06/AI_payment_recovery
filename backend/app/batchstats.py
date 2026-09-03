"""Cross-batch reference statistics — Phase 2.

Computed once per run. Root-cause attribution (``diagnose.py``) reads these to decide
whether an event is part of a concentration / temporal spike vs. background noise.

The seed only contains *failed* events (no successful-payment volume), so these are
share / lift / windowed-concentration signals, not true failure rates.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .models import Customer, RevenueEvent


def parse_ts(ts: str) -> datetime:
    """ISO-8601 'Z' string -> timezone-aware UTC datetime (matches seed.REFERENCE_NOW)."""
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _p75(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(0.75 * len(s)))]


@dataclass
class BatchStats:
    n: int
    n_by_type: Counter
    issuer_type: Counter  # (issuer, type) -> count
    gateway_type: Counter  # (gateway, type) -> count
    method_region: Counter  # (method, region) -> count
    region_totals: Counter  # region -> count
    n_issuers: int
    n_gateways: int
    issuer_times: dict[str, list[datetime]]
    gateway_times: dict[str, list[datetime]]
    all_times: list[datetime]
    global_issuer_share: dict[str, float]
    global_gateway_share: dict[str, float]
    at_risk_total: int
    amount_p75_by_type: dict[str, int] = field(default_factory=dict)

    # -- lift helpers ---------------------------------------------------------------
    def issuer_lift(self, issuer: str, etype: str) -> float:
        denom = max(1, self.n_by_type[etype])
        share = self.issuer_type[(issuer, etype)] / denom
        expected = 1.0 / max(1, self.n_issuers)
        return share / expected if expected else 0.0

    def gateway_lift(self, gateway: str, etype: str) -> float:
        denom = max(1, self.n_by_type[etype])
        share = self.gateway_type[(gateway, etype)] / denom
        expected = 1.0 / max(1, self.n_gateways)
        return share / expected if expected else 0.0

    def method_region_lift(self, method: str, region: str) -> float:
        total = sum(self.method_region.values()) or 1
        share = self.method_region[(method, region)] / total
        expected = (self.region_totals[region] / (self.n or 1)) * 0.5  # rough "expected UPI share of region"
        return share / expected if expected else 0.0

    # -- windowed concentration --------------------------------------------------
    def window_concentration(
        self, key_times: list[datetime], around: datetime, window_min: int = 110
    ) -> tuple[float, int]:
        """(key's share of ALL events in the +/- window, count of key events in window)."""
        lo, hi = around - timedelta(minutes=window_min), around + timedelta(minutes=window_min)
        key_in = sum(1 for t in key_times if lo <= t <= hi)
        total_in = sum(1 for t in self.all_times if lo <= t <= hi)
        return (key_in / total_in if total_in else 0.0), key_in


def compute_batch_stats(events: list[RevenueEvent], customers: list[Customer]) -> BatchStats:
    region_by_cust = {c.id: c.region for c in customers}
    n_by_type: Counter = Counter()
    issuer_type: Counter = Counter()
    gateway_type: Counter = Counter()
    method_region: Counter = Counter()
    region_totals: Counter = Counter()
    issuer_all: Counter = Counter()
    gateway_all: Counter = Counter()
    issuer_times: dict[str, list[datetime]] = {}
    gateway_times: dict[str, list[datetime]] = {}
    all_times: list[datetime] = []
    amounts_by_type: dict[str, list[int]] = {}

    for e in events:
        t = parse_ts(e.created_at)
        all_times.append(t)
        n_by_type[e.type] += 1
        issuer_type[(e.issuer, e.type)] += 1
        gateway_type[(e.gateway, e.type)] += 1
        issuer_all[e.issuer] += 1
        gateway_all[e.gateway] += 1
        region = region_by_cust.get(e.customer_id, "unknown")
        method_region[(e.method, region)] += 1
        region_totals[region] += 1
        issuer_times.setdefault(e.issuer, []).append(t)
        gateway_times.setdefault(e.gateway, []).append(t)
        amounts_by_type.setdefault(e.type, []).append(e.amount)

    n = len(events)
    for v in issuer_times.values():
        v.sort()
    for v in gateway_times.values():
        v.sort()
    all_times.sort()

    return BatchStats(
        n=n,
        n_by_type=n_by_type,
        issuer_type=issuer_type,
        gateway_type=gateway_type,
        method_region=method_region,
        region_totals=region_totals,
        n_issuers=len(issuer_all),
        n_gateways=len(gateway_all),
        issuer_times=issuer_times,
        gateway_times=gateway_times,
        all_times=all_times,
        global_issuer_share={k: v / n for k, v in issuer_all.items()},
        global_gateway_share={k: v / n for k, v in gateway_all.items()},
        at_risk_total=sum(e.amount for e in events),
        amount_p75_by_type={k: _p75(v) for k, v in amounts_by_type.items()},
    )
