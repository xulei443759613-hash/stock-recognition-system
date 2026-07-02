# Input / Output Playbook

Date: 2026-07-02

## Purpose

Keep the system easy to call from Codex, other AI agents, spreadsheets, and future UI tools without repeatedly loading the whole repository.

Recommended order:

1. `system-brief` for project-level context.
2. `review --format json-compact` for one stock.
3. `daily-timing` for daily timing on mentioned stocks.
4. `ai-brief` for short chat handoff.
5. `records/simulations.json` and `records/latest-simulation-summary.json` for current paper-trade state.

## Standard Inputs

### Group Message Review

Required:

- raw group message
- push date
- push time
- current price or `--auto-market-data`
- account value, default 34000

```powershell
python -m stock_recognition_system.cli review `
  --message-file msg.txt `
  --push-date 2026-07-02 `
  --push-time 09:30 `
  --auto-market-data `
  --account-value 34000 `
  --format json-compact
```

### Add To Simulation

Use this when the result is C/B tier or when the user is unsure.

```powershell
python -m stock_recognition_system.cli review `
  --message-file msg.txt `
  --current-price 10.00 `
  --account-value 34000 `
  --simulate
```

### Daily Buy Timing

Use this after mentioned stocks have been added to the simulation watchlist.

```powershell
python -m stock_recognition_system.cli daily-timing `
  --account-value 34000
python -m stock_recognition_system.cli daily-timing `
  --stock-code 002326 `
  --format json
```

The output action is conditional. `可考虑条件单` means "set a price alert or semi-auto condition at or below the system price, then confirm manually"; it does not mean market-buy now.

### Real Holding Monitor

Only use after the user confirms a real trade.

```powershell
python -m stock_recognition_system.cli holding-add `
  --stock-code 300001 `
  --buy-price 10.00 `
  --shares 100 `
  --stop-loss 9.50 `
  --take-profit 11.00
python -m stock_recognition_system.cli monitor
```

### External Candidate Research

This is research only.

```powershell
python -m stock_recognition_system.cli source-registry
python -m stock_recognition_system.cli research-wencai --query "今日强势但未涨停"
```

## Standard Outputs

| Output | Use |
| --- | --- |
| Markdown report | Human reading and audit |
| `json` | Full structured result |
| `json-compact` | Low-token single-stock handoff |
| `ai-brief` | Chat summary |
| `daily-timing` | Daily conditional timing for mentioned stocks |
| `system-brief` | Project-level context for Codex or another AI |
| `records/simulations.json` | Current paper simulation database |
| `records/latest-simulation-summary.json` | Latest after-close or manual refresh snapshot |
| `records/simulation_summaries.jsonl` | Historical simulation summaries |

## System Brief

Use this before handing the project to another AI:

```powershell
python -m stock_recognition_system.cli system-brief --format markdown --output records/system-brief.md
python -m stock_recognition_system.cli system-brief --format json --output records/system-brief.json
```

The brief includes:

- user profile and project positioning
- hard decision rules
- input and output contracts
- current simulation state
- external source policy
- next priorities

## Real-Trade Boundary

No output from `system-brief`, `research-wencai`, or external screeners is a buy command. A real 100-share training trade still needs:

- current price
- valid stop
- valid take-profit
- one-lot loss within beginner cap
- no hard veto
- A or B training tier
- user confirmation
