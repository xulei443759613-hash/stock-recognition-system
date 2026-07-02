from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .models import SourceTier


@dataclass(frozen=True)
class ExternalSourceRegistration:
    source_id: str
    provider: str
    source_tier: SourceTier
    auth_required: bool
    auth_modes: tuple[str, ...]
    enabled_by_default: bool
    can_drive_decision: bool
    decision_scope: str
    data_fields: tuple[str, ...]
    license_warning: str = ""
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["source_tier"] = self.source_tier.value
        payload["auth_modes"] = list(self.auth_modes)
        payload["data_fields"] = list(self.data_fields)
        payload["notes"] = list(self.notes)
        return payload


_SOURCES: tuple[ExternalSourceRegistration, ...] = (
    ExternalSourceRegistration(
        source_id="tencent_public",
        provider="Tencent public quote",
        source_tier=SourceTier.EXCHANGE_MARKET_DATA,
        auth_required=False,
        auth_modes=("none",),
        enabled_by_default=True,
        can_drive_decision=True,
        decision_scope="market_price_and_ohlc_only",
        data_fields=("current_price", "intraday_price", "ohlc", "volume", "turnover_rate"),
        notes=("Used as a market-data fallback and message-time price source.",),
    ),
    ExternalSourceRegistration(
        source_id="eastmoney_public",
        provider="EastMoney public quote",
        source_tier=SourceTier.EXCHANGE_MARKET_DATA,
        auth_required=False,
        auth_modes=("none",),
        enabled_by_default=True,
        can_drive_decision=True,
        decision_scope="market_price_and_ohlc_only",
        data_fields=("current_price", "change_pct", "ohlc", "turnover_rate"),
        notes=("K-line endpoint may fail; real-time endpoint is used as fallback.",),
    ),
    ExternalSourceRegistration(
        source_id="tushare_optional",
        provider="Tushare",
        source_tier=SourceTier.LICENSED_DATA_VENDOR,
        auth_required=True,
        auth_modes=("token",),
        enabled_by_default=False,
        can_drive_decision=True,
        decision_scope="market_and_fundamental_evidence",
        data_fields=("daily", "financials", "index", "concept", "moneyflow"),
        license_warning="Requires a user-provided Tushare token and quota compliance.",
    ),
    ExternalSourceRegistration(
        source_id="ifind_optional",
        provider="Tonghuashun iFind",
        source_tier=SourceTier.LICENSED_DATA_VENDOR,
        auth_required=True,
        auth_modes=("account", "sdk", "token"),
        enabled_by_default=False,
        can_drive_decision=True,
        decision_scope="market_and_fundamental_evidence",
        data_fields=("quote", "historical_series", "financials", "wencai_query", "indices"),
        license_warning="Use only with legal iFind access. Do not store credentials in the repository.",
    ),
    ExternalSourceRegistration(
        source_id="wencai_research",
        provider="Tonghuashun WenCai",
        source_tier=SourceTier.UNKNOWN,
        auth_required=True,
        auth_modes=("manual_export", "cookie"),
        enabled_by_default=False,
        can_drive_decision=False,
        decision_scope="candidate_discovery_only",
        data_fields=("candidate_code", "candidate_name", "screening_reason", "rank_fields"),
        license_warning="Community or browser-based access is fragile and may involve cookies. Research only.",
        notes=("Candidates must still pass review, risk checks, and simulation before any real trade.",),
    ),
    ExternalSourceRegistration(
        source_id="pywencai_community",
        provider="pywencai community package",
        source_tier=SourceTier.UNKNOWN,
        auth_required=True,
        auth_modes=("cookie",),
        enabled_by_default=False,
        can_drive_decision=False,
        decision_scope="candidate_discovery_only",
        data_fields=("candidate_dataframe",),
        license_warning="Disabled by default. Do not run high-frequency scraping or store cookies.",
    ),
    ExternalSourceRegistration(
        source_id="iwencai_cli_research",
        provider="iwencai-cli browser automation",
        source_tier=SourceTier.UNKNOWN,
        auth_required=True,
        auth_modes=("browser_session", "cookie"),
        enabled_by_default=False,
        can_drive_decision=False,
        decision_scope="manual_research_only",
        data_fields=("candidate_json",),
        license_warning="Browser automation is fragile and should not be part of the production data layer.",
    ),
)


def list_external_sources() -> list[ExternalSourceRegistration]:
    return list(_SOURCES)


def get_external_source(source_id: str) -> ExternalSourceRegistration:
    normalized = source_id.strip().lower()
    for source in _SOURCES:
        if source.source_id == normalized:
            return source
    raise KeyError(f"Unknown external source: {source_id}")


def build_research_stub(source_id: str, query: str, as_of: str | None = None) -> dict[str, object]:
    source = get_external_source(source_id)
    timestamp = as_of or datetime.now().astimezone().replace(microsecond=0).isoformat()
    return {
        "source": source.source_id,
        "provider": source.provider,
        "query": query,
        "as_of": timestamp,
        "status": "disabled",
        "decision_scope": source.decision_scope,
        "can_drive_decision": source.can_drive_decision,
        "warnings": [
            source.license_warning or "Research-only source.",
            "No external query was executed.",
            "Candidates from this source must still pass local review and simulation.",
        ],
        "candidates": [],
    }
