"""Root-cause attribution — Phase 2 (SPEC.md §16).

Deterministic. The LLM never runs here and never picks the cause — Phase 4 only writes a
narrative around the ``(cause, confidence, evidence)`` this returns.

Method: collect weighted ``(cause, weight, evidence_fragment)`` signals from direct error
codes + cross-batch concentration / temporal clustering, sum per cause, take argmax.
Below ``CONFIDENCE_THRESHOLD`` the cause is gated to ``undetermined``.
"""

from __future__ import annotations

from .batchstats import BatchStats, parse_ts
from .config import CONFIDENCE_THRESHOLD
from .enums import Cause, EventType
from .models import Customer, RevenueEvent

MAX_CONF = 0.97

_PAY_TYPES = {EventType.payment_failed.value, EventType.subscription_failed.value}


def run_root_cause(
    event: RevenueEvent, customer: Customer, stats: BatchStats
) -> tuple[str, float, dict]:
    meta = event.meta or {}
    et = event.type
    created = parse_ts(event.created_at)
    signals: list[tuple[Cause, float, dict]] = []

    # -- direct hints ---------------------------------------------------------------
    hint = meta.get("error_code") or meta.get("decline_code")
    if hint == "issuer_unavailable":
        signals.append((Cause.issuer_downtime, 0.56, {"error_code": hint}))
    elif hint == "gateway_timeout":
        signals.append((Cause.gateway_degradation, 0.56, {"error_code": hint}))
    elif hint == "upi_response_timeout":
        signals.append((Cause.upi_timeout, 0.48, {"error_code": hint}))
    elif hint == "insufficient_funds":
        signals.append((Cause.insufficient_funds_salary_cycle, 0.42, {"decline_code": hint}))
    elif hint == "expired_card":
        signals.append((Cause.card_expired, 0.55, {"decline_code": hint}))
    if meta.get("mandate_status") == "revoked":
        signals.append((Cause.mandate_revoked, 0.60, {"mandate_status": "revoked"}))
    if meta.get("chargeback") or meta.get("dispute_flag"):
        signals.append((Cause.disputed, 0.65, {"dispute": True}))

    # -- payment / subscription: issuer & gateway incidents, UPI region, salary cycle
    if et in _PAY_TYPES:
        il = stats.issuer_lift(event.issuer, et)
        if il >= 2.0:
            share, cnt = stats.window_concentration(stats.issuer_times.get(event.issuer, []), created)
            ratio = share / max(stats.global_issuer_share.get(event.issuer, 1e-6), 1e-6)
            if ratio >= 2.2 and cnt >= 6:
                w = 0.30 + 0.25 * min((ratio - 2.2) / 3, 1.0)
                signals.append(
                    (
                        Cause.issuer_downtime,
                        w,
                        {
                            "signal": "issuer_incident",
                            "issuer": event.issuer,
                            "issuer_lift": round(il, 2),
                            "window_share": round(share, 2),
                            "window_events": cnt,
                        },
                    )
                )
            elif il >= 3.0:
                signals.append(
                    (Cause.issuer_downtime, 0.20, {"signal": "issuer_concentration", "issuer": event.issuer, "issuer_lift": round(il, 2)})
                )

        gl = stats.gateway_lift(event.gateway, et)
        share, cnt = stats.window_concentration(stats.gateway_times.get(event.gateway, []), created)
        ratio = share / max(stats.global_gateway_share.get(event.gateway, 1e-6), 1e-6)
        if ratio >= 2.2 and cnt >= 6 and gl >= 1.1:
            w = 0.28 + 0.24 * min((ratio - 2.2) / 3, 1.0)
            signals.append(
                (
                    Cause.gateway_degradation,
                    w,
                    {
                        "signal": "gateway_incident",
                        "gateway": event.gateway,
                        "gateway_lift": round(gl, 2),
                        "window_share": round(share, 2),
                        "window_events": cnt,
                    },
                )
            )

        if event.method == "upi":
            mrl = stats.method_region_lift("upi", customer.region)
            android = meta.get("device") == "android"
            if android or mrl >= 1.4:
                w = 0.16 + (0.24 if android else 0.0) + (0.15 if mrl >= 1.8 else 0.0)
                signals.append(
                    (
                        Cause.upi_timeout,
                        w,
                        {"signal": "upi_region_device", "region": customer.region, "method_region_lift": round(mrl, 2), "android": android},
                    )
                )

        if created.day <= 3:
            signals.append((Cause.insufficient_funds_salary_cycle, 0.25, {"signal": "first_of_month", "day": created.day}))

    if et == EventType.subscription_failed.value and event.method == "card" and not meta.get("mandate_status"):
        signals.append((Cause.card_expired, 0.30, {"signal": "card_subscription"}))

    # -- checkout: latency vs shipping shock -------------------------------------
    if et == EventType.checkout_abandoned.value:
        lat = int(meta.get("latency_ms", 0))
        ship = int(meta.get("shipping_fee", 0))
        cart = int(meta.get("cart_value") or event.amount or 1)
        if lat >= 1500:
            signals.append((Cause.checkout_latency, 0.50 + 0.25 * min((lat - 1500) / 2500, 1.0), {"signal": "latency", "latency_ms": lat}))
        ratio = ship / cart if cart else 0.0
        if ship >= 150 or ratio >= 0.12:
            signals.append(
                (Cause.price_shock_shipping, 0.52 + 0.20 * min(ratio / 0.3, 1.0), {"signal": "shipping_shock", "shipping_fee": ship, "shipping_ratio": round(ratio, 2)})
            )
        if not signals:
            signals.append((Cause.forgot_to_pay, 0.22, {"signal": "checkout_no_marker"}))

    # -- invoice: default forgot-to-pay unless a dispute/mandate hint fired -----
    if et == EventType.invoice_overdue.value:
        if not any(s[0] in (Cause.disputed, Cause.mandate_revoked) for s in signals):
            signals.append((Cause.forgot_to_pay, 0.55, {"signal": "invoice_ageing", "days_overdue": meta.get("days_overdue")}))

    if not signals:
        signals.append((Cause.undetermined, 0.20, {"signal": "no_signal"}))

    # -- aggregate ----------------------------------------------------------------
    score: dict[Cause, float] = {}
    frags: dict[Cause, dict] = {}
    for cause, w, frag in signals:
        score[cause] = min(MAX_CONF, score.get(cause, 0.0) + w)
        frags.setdefault(cause, {}).update(frag)

    ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    winner, conf = ranked[0][0], round(ranked[0][1], 3)
    evidence = dict(frags[winner])
    if len(ranked) > 1:
        evidence["runner_up"] = {"cause": ranked[1][0].value, "score": round(ranked[1][1], 3)}

    if conf < CONFIDENCE_THRESHOLD:
        evidence["gated"] = {"raw_cause": winner.value, "raw_confidence": conf, "threshold": CONFIDENCE_THRESHOLD}
        return Cause.undetermined.value, conf, evidence
    return winner.value, conf, evidence
