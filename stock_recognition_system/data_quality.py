from __future__ import annotations

from .models import InformationSource, SourceTier


CLEAN_SOURCE_TIERS = {
    SourceTier.OFFICIAL_DISCLOSURE,
    SourceTier.EXCHANGE_MARKET_DATA,
    SourceTier.LICENSED_DATA_VENDOR,
}


def source_quality_notes(sources: list[InformationSource]) -> list[str]:
    if not sources:
        return ["未记录数据来源，不能把结论视为已核验"]

    notes: list[str] = []
    clean_sources = [source for source in sources if source.tier in CLEAN_SOURCE_TIERS]
    group_sources = [source for source in sources if source.tier == SourceTier.GROUP_MESSAGE]

    if clean_sources:
        names = "、".join(source.name for source in clean_sources)
        notes.append(f"已记录干净数据源：{names}")
    else:
        notes.append("缺官方披露、交易所行情或合规数据供应商来源")

    if group_sources:
        notes.append("群消息只能作为线索，不能作为买入证据")

    unknown_sources = [source for source in sources if source.tier == SourceTier.UNKNOWN]
    if unknown_sources:
        names = "、".join(source.name for source in unknown_sources)
        notes.append(f"存在未知来源：{names}")

    return notes
