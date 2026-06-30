from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .models import FollowUpTask, ReviewResult


def build_follow_up_tasks(result: ReviewResult, base_date: date | None = None) -> list[FollowUpTask]:
    base_date = base_date or date.today()
    parsed = result.parsed
    stock_code = parsed.stock_code if parsed else None
    stock_name = parsed.stock_name if parsed else None
    source = "group"

    if not parsed:
        return []

    checks = [
        (1, "next_day", "记录次日开盘、收盘、是否高开低走，验证尾盘推送风险"),
        (3, "three_day", "记录 3 日内是否触及入场区间、止损价或目标价"),
        (5, "five_day", "记录 5 日表现，判断群消息是否追高或有效"),
        (10, "ten_day", "记录 10 日表现，用于群源质量评分"),
    ]
    return [
        FollowUpTask(
            stock_code=stock_code,
            stock_name=stock_name,
            source=source,
            due_date=(base_date + timedelta(days=days)).isoformat(),
            task_type=task_type,
            instruction=instruction,
        )
        for days, task_type, instruction in checks
    ]


def append_follow_up_tasks(record_dir: str | Path, tasks: list[FollowUpTask]) -> Path:
    record_dir = Path(record_dir)
    record_dir.mkdir(parents=True, exist_ok=True)
    path = record_dir / "followups.jsonl"
    with path.open("a", encoding="utf-8") as file:
        for task in tasks:
            file.write(json.dumps(asdict(task), ensure_ascii=False) + "\n")
    return path


def load_pending_follow_ups(record_dir: str | Path, as_of: date | None = None) -> list[FollowUpTask]:
    as_of = as_of or date.today()
    path = Path(record_dir) / "followups.jsonl"
    if not path.exists():
        return []

    tasks: list[FollowUpTask] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("status", "pending") == "pending" and raw.get("due_date", "9999-12-31") <= as_of.isoformat():
                tasks.append(FollowUpTask(**raw))
    return tasks
