# Architecture

当前项目保留 `stock_recognition_system/` 包结构，不迁移到 `src/`。完整交易系统规格见 `docs/trading-system-spec.md`，当前采纳计划见 `docs/TRADING_SYSTEM_ADOPTION.md`。

## 模块职责

- `parser.py`：群消息解析。
- `rules.py`：红线、硬性否决、证据评分、时机判断。
- `technical.py`：轻量技术面体检。
- `risk.py`：盈亏比、仓位、基础止盈止损。
- `short_term.py`：4-5 日短线训练仓计划。
- `opportunity.py`：机会评级和错失机会复盘口径。
- `exit_suggestion.py`：系统建议止盈止损。
- `training.py`：A/B/C/D 训练档位和 100 股执行清单。
- `evidence_playbook.py`：推荐逻辑到证据采集计划的映射。
- `eastmoney.py` / `tencent.py`：公开行情数据源。
- `engine.py`：主编排流程。
- `reporting.py`：Markdown 报告。
- `records.py` / `followup.py`：复盘记录、群源评分、任务管理。
- `cli.py`：命令行入口。

## 数据流

```text
群消息 -> parser -> rules/evidence/market data -> engine
      -> risk/short_term/opportunity/exit_suggestion/training
      -> reporting -> records/followup
```

## 设计原则

- 数据源失败时降级，不猜测补数据。
- 所有真实仓位动作必须先过硬性否决。
- 系统建议价位只作为风控计划，不构成投资建议。
- 回测和策略层进入项目前，必须先累计足够复盘样本。

## 与完整规格的关系

`docs/trading-system-spec.md` 是未来完整交易系统蓝图；当前项目只采纳其中与新手风控直接相关的部分。市场状态、多时间框架、策略注册器、回测框架按 `docs/tasks.md` 分阶段实现。
