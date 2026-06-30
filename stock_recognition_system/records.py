from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import ReviewResult, SignalAction


def append_daily_record(record_dir: str | Path, stock_label: str, result: ReviewResult, summary: str) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / f"{datetime.now():%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(f"# Stock Group Signal Records - {datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n## {datetime.now():%H:%M:%S} - {stock_label}\n\n")
        file.write(f"- signal: {result.action.value}\n")
        file.write(f"- confidence: {result.confidence}\n")
        file.write(f"- max_position_pct: {result.max_position_pct:.2%}\n")
        file.write(f"- summary: {summary}\n")
    return path


def append_review_report(record_dir: str | Path, result: ReviewResult, summary: str = "") -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / f"{datetime.now():%Y-%m-%d}.md"
    if not path.exists():
        path.write_text(f"# Stock Group Signal Records - {datetime.now():%Y-%m-%d}\n", encoding="utf-8")

    parsed = result.parsed
    stock_label = "未知股票"
    if parsed and parsed.stock_name and parsed.stock_code:
        stock_label = f"{parsed.stock_name} {parsed.stock_code}"
    elif parsed and parsed.stock_code:
        stock_label = parsed.stock_code

    with path.open("a", encoding="utf-8") as file:
        file.write(f"\n\n---\n\n## {datetime.now():%H:%M:%S} - {stock_label}\n\n")
        if summary:
            file.write(f"> {summary}\n\n")
        file.write(result.report or f"- signal: {result.action.value}\n")
        file.write("\n")
    return path


@dataclass
class SourceOutcome:
    action: SignalAction
    reached_target: bool = False
    hit_stop_loss: bool = False
    late_push: bool = False
    chased_after_target: bool = False


def score_source_quality(outcomes: list[SourceOutcome]) -> dict[str, object]:
    total = len(outcomes)
    if total == 0:
        return {"sample_size": 0, "grade": "无样本", "notes": ["没有复盘记录"]}

    target_hits = sum(1 for item in outcomes if item.reached_target)
    stop_hits = sum(1 for item in outcomes if item.hit_stop_loss)
    late_pushes = sum(1 for item in outcomes if item.late_push)
    chase_cases = sum(1 for item in outcomes if item.chased_after_target)
    abandon_count = sum(1 for item in outcomes if item.action == SignalAction.ABANDON)

    notes: list[str] = []
    score = 60
    score += int(25 * target_hits / total)
    score -= int(30 * stop_hits / total)
    score -= int(20 * late_pushes / total)
    score -= int(20 * chase_cases / total)

    if total < 20:
        notes.append("样本少于 20 条，只能观察，不能评价群源优劣")
    if stop_hits / total >= 0.3:
        notes.append("止损触发比例偏高")
    if late_pushes / total >= 0.3:
        notes.append("尾盘推送比例偏高")
    if chase_cases:
        notes.append("存在超过目标或涨停后推送的追高样本")
    if abandon_count / total >= 0.5:
        notes.append("系统放弃比例较高，群消息噪声偏多")

    score = max(0, min(100, score))
    if total < 20:
        grade = "样本不足"
    elif score >= 75:
        grade = "可继续观察"
    elif score >= 55:
        grade = "谨慎观察"
    else:
        grade = "建议远离"

    return {
        "sample_size": total,
        "grade": grade,
        "score": score,
        "target_hit_rate": round(target_hits / total, 4),
        "stop_loss_rate": round(stop_hits / total, 4),
        "late_push_rate": round(late_pushes / total, 4),
        "chase_case_rate": round(chase_cases / total, 4),
        "notes": notes,
    }
