# External Data Skills Review

Date: 2026-07-02

## Conclusion

GitHub has several Tonghuashun / WenCai / A-share data skills or tools, but none should be blindly installed as the decision engine for this project.

The correct product strategy is:

1. Keep the local Python system as the source of truth for risk rules, simulation, holdings, and records.
2. Use Tonghuashun/iFind/WenCai only as optional evidence or candidate discovery sources.
3. Never let an external screener upgrade a signal into a real buy by itself.
4. Any external data source must write source, timestamp, auth mode, warnings, and whether it is official or community-scraped.

## Reviewed Projects

| Project | Type | Useful Parts | Risk | Adoption Decision |
| --- | --- | --- | --- | --- |
| `10e9928a/ifind-data` | CodeBuddy Skill, based on Tonghuashun iFind API | Real-time quotes, historical series, financial data, WenCai query, indices, funds | Needs iFind account/API permission, local SDK or token | Good candidate only if user has legal iFind access |
| `simonlin1212/a-stock-data` | Claude-style A-share data Skill | Multi-layer data architecture, source failover, concepts, announcements, rankings, capital flow | Very broad surface area, large unreviewed Skill, not tailored to beginner risk controls | Learn architecture, do not import wholesale |
| `zsrl/pywencai` | Python package for WenCai | Natural-language stock screening, returns DataFrame | Community tool, requires cookie, low-frequency only, legal/technical risk | Optional research adapter only, disabled by default |
| `shaw-baobao/iwencai-cli` | Local CLI using Chrome/Playwright | Natural-language screening with JSON output | Browser automation, session/cookie dependency, fragile under UI changes | Optional manual research workflow, not production data layer |
| `openstockdata/stock-data-skill` | OpenClaw stock/crypto data skill | Multi-source failover idea | Needs separate review before trust | Watchlist only |
| `Tushare-Finance-Skill-for-Claude-Code` | Tushare skill | Broad official-style API coverage | Needs Tushare token and quota | Better long-term clean source than scraped WenCai if token exists |

## Adoption Rules

### Allowed

- Use WenCai/iFind to answer exploratory questions such as:
  - "今日强势但未涨停且换手小于 8% 的股票"
  - "近 5 日放量突破但未创新高"
  - "行业热度排名"
  - "机构一致预期或研报数量"
- Store the result as evidence, not as an action.
- Cross-check any candidate with current system rules:
  - no target/stop means only observe or simulate
  - no current price means no executable trade
  - limit-up or above target means no chasing
  - risk/reward and one-lot loss must pass

### Not Allowed

- Do not put user cookies or brokerage credentials into the repository.
- Do not use WenCai output as a direct buy/sell command.
- Do not run high-frequency scraping.
- Do not import a 100KB+ external Skill wholesale into this project without review.
- Do not loosen hard vetoes because an external screener says a stock is hot.

## Product Optimization Plan

### P1: External Source Registry

Add a small source registry before integrating any new provider:

- `source_id`
- `provider`
- `source_tier`
- `auth_required`
- `license_warning`
- `last_success_at`
- `data_fields`
- `can_drive_decision`

Default rule: external community/scraped sources can never drive real-trade decisions.

### P1: WenCai Research Adapter

If a cookie or compliant API is available later, add a disabled-by-default adapter:

```text
research-wencai --query "近5日放量上涨但未涨停，换手率小于8%，市值小于300亿"
```

Output should be JSON only:

```json
{
  "source": "wencai",
  "query": "...",
  "auth_mode": "manual_cookie",
  "as_of": "2026-07-02T10:00:00+08:00",
  "warnings": ["community source; research only"],
  "candidates": []
}
```

### P2: Candidate To Review Pipeline

Add a command to convert external candidates into system reviews:

```text
candidate-review --candidate-file records/wencai-candidates.json
```

Each candidate must still pass:

- current price check
- hard vetoes
- system stop/take-profit generation
- training tier
- simulation before real trade

## Current Decision

Do not install a Tonghuashun/WenCai skill today. The current system should first add a source registry and clean research-adapter boundary. After that, use iFind if legal access exists; otherwise, only use WenCai-style tools manually and low-frequency for candidate discovery.
