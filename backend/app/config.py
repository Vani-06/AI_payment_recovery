"""Runtime config + tuning constants — Phase 0.

Business knobs live here so Phase 9 tuning is a one-file diff. Nothing here is secret
except what comes from the environment via `Settings`.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import Channel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://sherlock:sherlock@localhost:5433/sherlock"
    anthropic_api_key: str | None = None
    sherlock_model: str = "claude-sonnet-5"
    frontend_origin: str = "http://localhost:3000"
    demo_seed: int = 7

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()

# --- Compliance / stopping-rule thresholds (SPEC §8) -------------------------------------
CONTACT_CAP_PER_7D = 3
CHANNEL_COOLDOWN_HOURS = 24
QUIET_HOURS_START = 21  # inclusive, IST
QUIET_HOURS_END = 9  # exclusive, IST
GLOBAL_OUTREACH_CAP = 320  # per batch run
DISCOUNT_MAX_PCT = 10
DISCOUNT_MAX_USES_PER_CUSTOMER = 1

# --- Economics (SPEC §17) -------------------------------------------------------------
#: Per-send unit cost in whole INR.
CHANNEL_COST: dict[Channel, int] = {
    Channel.whatsapp: 3,
    Channel.email: 1,
    Channel.sms: 2,
    Channel.voice: 25,
    Channel.finance_touch: 150,
    Channel.none: 0,
}

# --- Intelligence layer (SPEC §16) -------------------------------------------------------
#: Below this, diagnosis.cause becomes `undetermined` -> conservative action only.
CONFIDENCE_THRESHOLD = 0.55

# --- Seed generator (SPEC §4) ---------------------------------------------------------
SEED_EVENT_COUNT = 400
SEED_CUSTOMER_COUNT = 180
REGIONS = ("south", "west", "north", "east")
GATEWAYS = ("razorpay_pg_a", "razorpay_pg_b", "razorpay_pg_c")
METHODS = ("upi", "card", "netbanking", "wallet")
ISSUERS = ("ICICI", "HDFC", "SBI", "Axis", "Kotak", "Visa", "Mastercard", "RuPay")
