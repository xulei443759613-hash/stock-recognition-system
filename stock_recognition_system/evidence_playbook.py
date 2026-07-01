from __future__ import annotations

from collections.abc import Iterable

from .models import EvidenceRequirement


BASELINE_REQUIREMENTS = [
    EvidenceRequirement(
        claim="消息时点价格",
        category="行情时点",
        priority="P0",
        required_sources=["腾讯分时/交易所行情", "券商成交页截图（人工备份）"],
        collect=["推送日期和时间", "消息时点或此前最近一分钟价格", "当时涨跌幅", "是否涨停或接近涨停"],
        pass_criteria=["消息时点价格未超过目标价", "消息时点价格未涨停", "价格没有明显脱离入场上沿"],
        reject_criteria=["缺消息时点价格", "消息时点价格已超过目标价", "消息时点已涨停或接近涨停"],
        notes=["这是新手短线模式的第一道门槛，没有它只允许观察或模拟。"],
    ),
    EvidenceRequirement(
        claim="20日价格结构",
        category="技术面体检",
        priority="P0",
        required_sources=["东方财富/腾讯日线行情", "交易所行情数据"],
        collect=["最近20个收盘价", "5日涨跌幅", "20日涨跌幅", "换手率", "量比"],
        pass_criteria=["未出现短期过热", "没有跌破关键均线后的弱势结构", "换手和量比没有异常失真"],
        reject_criteria=["5日涨幅过大后才推送", "20日涨幅过热", "量比极端放大且价格已脱离入场区"],
        notes=["技术面只用于过滤追高和破位，不单独作为买入理由。"],
    ),
    EvidenceRequirement(
        claim="账户承受力",
        category="仓位风控",
        priority="P0",
        required_sources=["账户资金人工输入", "系统仓位规则"],
        collect=["账户总额", "训练仓上限", "100股成本", "买100股到止损的亏损金额"],
        pass_criteria=["100股成本不超过训练仓现金上限", "100股止损亏损不超过单笔最大亏损"],
        reject_criteria=["100股成本超出训练仓", "100股止损亏损超出单笔最大亏损"],
        notes=["A股最小100股，新手小资金必须先过这一关。"],
    ),
]


def build_evidence_requirements(
    claims: Iterable[str],
    *,
    include_baseline: bool = True,
) -> list[EvidenceRequirement]:
    requirements: list[EvidenceRequirement] = list(BASELINE_REQUIREMENTS) if include_baseline else []
    seen: set[str] = {item.claim for item in requirements}

    for raw_claim in claims:
        claim = raw_claim.strip()
        if not claim or claim in seen:
            continue
        requirements.append(_requirement_for_claim(claim))
        seen.add(claim)

    return requirements


def _requirement_for_claim(claim: str) -> EvidenceRequirement:
    if _contains_any(claim, ["基金", "社保", "北向", "陆股通", "机构参与", "机构持仓", "加仓"]):
        return EvidenceRequirement(
            claim=claim,
            category="机构持仓",
            priority="P1",
            required_sources=["巨潮资讯定期报告", "交易所公告", "Tushare/AkShare结构化持仓数据（辅助）"],
            collect=["最近一期报告日期", "持仓主体名称", "持仓数量和比例", "上一期持仓变化"],
            pass_criteria=["最近一期正式披露显示持有或增持", "持仓主体名称和群消息描述一致"],
            reject_criteria=["正式披露未显示相关持仓", "数据停留在过旧报告期", "只来自营销话术或截图"],
            notes=["机构持仓通常有滞后，只能验证事实，不能证明短线4-5日一定上涨。"],
        )

    if _contains_any(claim, ["游资", "龙虎榜", "控盘", "高控盘", "资金热度", "主力", "抢筹"]):
        return EvidenceRequirement(
            claim=claim,
            category="交易行为",
            priority="P0",
            required_sources=["交易所龙虎榜", "交易所/行情成交数据", "东方财富/腾讯行情（辅助）"],
            collect=["龙虎榜日期和席位", "买入/卖出净额", "成交额", "换手率", "量比", "分时价格位置"],
            pass_criteria=["只能确认短线活跃或资金参与", "价格仍在系统可接受入场范围内"],
            reject_criteria=["没有龙虎榜或成交证据", "高换手后已明显追高", "用控盘、高控盘包装不可验证结论"],
            notes=["控盘/高控盘默认视为风险话术，不能作为买入证据。"],
        )

    if _contains_any(claim, ["盈利", "业绩", "毛利", "现金流", "收入", "基本面", "困境反转", "拐点"]):
        return EvidenceRequirement(
            claim=claim,
            category="财务质量",
            priority="P1",
            required_sources=["巨潮资讯定期报告", "交易所公告", "公司财报原文", "Tushare财务数据（辅助）"],
            collect=["营业收入同比/环比", "归母净利润同比/环比", "毛利率变化", "经营现金流净额", "应收和存货变化"],
            pass_criteria=["最近两期关键指标改善", "经营现金流不明显背离利润", "财报原文能对应群消息说法"],
            reject_criteria=["利润改善来自一次性收益", "现金流恶化", "毛利率或收入未改善", "只有研报口径没有财报支撑"],
            notes=["财务证据适合提高可信度，但短线执行仍受价格和止损风险约束。"],
        )

    if _contains_any(claim, ["评级", "研报", "目标价", "买入评级", "增持评级"]):
        return EvidenceRequirement(
            claim=claim,
            category="外部评级",
            priority="P2",
            required_sources=["券商研报原文", "合规数据商研报库", "公司公告中可核实的信息"],
            collect=["机构名称", "发布日期", "评级", "目标价", "核心假设", "是否滞后或付费摘录"],
            pass_criteria=["研报主体、日期和评级可核实", "核心假设能被公告或财报交叉验证"],
            reject_criteria=["只看到二手摘录", "研报过旧", "评级依据无法和公告/财报对应"],
            notes=["评级是弱证据，不能替代价格、财报和风险控制。"],
        )

    if _contains_any(claim, ["调研", "投资者关系", "机构来访"]):
        return EvidenceRequirement(
            claim=claim,
            category="调研记录",
            priority="P1",
            required_sources=["巨潮资讯投资者关系活动记录", "交易所互动易/上证e互动", "公司公告"],
            collect=["调研日期", "机构名单", "问答要点", "是否涉及未公开重大信息"],
            pass_criteria=["调研记录公开可查", "问答要点和推荐逻辑一致"],
            reject_criteria=["无公开记录", "用调研包装内幕或确定性收益"],
            notes=["公开调研只能说明信息披露，不代表短线买点成立。"],
        )

    if _contains_any(claim, ["材料", "封装", "涨价", "行业", "题材", "景气", "概念"]):
        return EvidenceRequirement(
            claim=claim,
            category="行业题材",
            priority="P2",
            required_sources=["公司公告", "行业协会/权威价格指数", "交易所互动平台", "可信财经媒体"],
            collect=["产品或题材对应收入占比", "产品价格趋势", "公司是否公告确认", "行业事件日期"],
            pass_criteria=["公司确有相关业务暴露", "行业价格或事件能被权威来源确认"],
            reject_criteria=["只有题材标签", "公司收入占比很低", "事件已经被价格充分反映"],
            notes=["题材只做背景信息，不能绕过盈亏比和止损规则。"],
        )

    return EvidenceRequirement(
        claim=claim,
        category="未分类逻辑",
        priority="P2",
        required_sources=["公司公告", "定期报告", "交易所问询/回复", "可信数据源"],
        collect=["原始出处", "发生日期", "可量化指标", "是否能和推荐逻辑一一对应"],
        pass_criteria=["至少一个官方或合规来源能直接支持该说法"],
        reject_criteria=["没有原始出处", "只来自群消息或截图", "无法量化或无法复核"],
        notes=["未知逻辑默认降权，先当作待核验线索。"],
    )


def _contains_any(value: str, keywords: list[str]) -> bool:
    return any(keyword in value for keyword in keywords)
