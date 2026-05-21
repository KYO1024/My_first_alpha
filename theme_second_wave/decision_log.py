from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .dashboard import STAGE_LABELS
from .decision_support import bear_case, bull_case, execution_condition, is_focus_signal, risk_check
from .models import ScanResult, WaveStage


DEFAULT_HORIZONS = (1, 3, 5, 10)


@dataclass(frozen=True)
class DecisionLogSummary:
    jsonl_path: Path
    markdown_path: Path
    added_count: int
    updated_count: int
    open_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "jsonl_path": str(self.jsonl_path),
            "markdown_path": str(self.markdown_path),
            "added_count": self.added_count,
            "updated_count": self.updated_count,
            "open_count": self.open_count,
        }


def update_decision_log(
    *,
    results: list[ScanResult],
    report_dir: str | Path,
    generated_at: datetime | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> DecisionLogSummary:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "decision_log.jsonl"
    markdown_path = output_dir / "decision_log.md"
    now = generated_at or datetime.now(ZoneInfo("Asia/Shanghai"))

    entries = _load_entries(jsonl_path)
    updated_count = _update_outcomes(entries, results, horizons)
    added_count = _append_new_entries(entries, results, now)
    _write_entries(jsonl_path, entries)
    _write_markdown(markdown_path, entries)
    open_count = sum(1 for entry in entries if not entry.get("closed"))
    return DecisionLogSummary(
        jsonl_path=jsonl_path,
        markdown_path=markdown_path,
        added_count=added_count,
        updated_count=updated_count,
        open_count=open_count,
    )


def build_decision_entry(item: ScanResult, recorded_at: datetime) -> dict[str, Any]:
    latest_date = str(item.metrics.get("latest_date") or recorded_at.date().isoformat())
    signal_id = _signal_id(item, latest_date)
    return {
        "signal_id": signal_id,
        "recorded_at": recorded_at.isoformat(timespec="seconds"),
        "signal_date": latest_date,
        "code": item.candidate.code,
        "name": item.candidate.name,
        "theme": item.candidate.theme,
        "sector": item.candidate.sector,
        "stage": item.stage.value,
        "stage_label": STAGE_LABELS[item.stage],
        "score": item.score,
        "current_price": item.current_price,
        "trigger_price": item.trigger_price,
        "trigger_distance_pct": item.metrics.get("trigger_distance_pct"),
        "invalidation_price": item.invalidation_price,
        "latest_date": latest_date,
        "data_source": item.metrics.get("data_source"),
        "bull_case": bull_case(item),
        "bear_case": bear_case(item),
        "risk_check": risk_check(item),
        "execution_condition": execution_condition(item),
        "action": item.action,
        "outcomes": {},
        "hit_trigger": False,
        "hit_invalidation": False,
        "closed": item.stage == WaveStage.SECOND_WAVE_CONFIRMED,
    }


def _append_new_entries(entries: list[dict[str, Any]], results: list[ScanResult], now: datetime) -> int:
    existing_ids = {str(entry.get("signal_id")) for entry in entries}
    added = 0
    for item in results:
        if not is_focus_signal(item):
            continue
        latest_date = str(item.metrics.get("latest_date") or now.date().isoformat())
        signal_id = _signal_id(item, latest_date)
        if signal_id in existing_ids:
            continue
        entries.append(build_decision_entry(item, now))
        existing_ids.add(signal_id)
        added += 1
    return added


def _update_outcomes(
    entries: list[dict[str, Any]],
    results: list[ScanResult],
    horizons: tuple[int, ...],
) -> int:
    by_code = {item.candidate.code: item for item in results if item.current_price is not None}
    updated = 0
    for entry in entries:
        item = by_code.get(str(entry.get("code")))
        if item is None or item.current_price is None:
            continue
        signal_price = _float_or_none(entry.get("current_price"))
        signal_date = _date_or_none(entry.get("signal_date"))
        current_date = _date_or_none(item.metrics.get("latest_date"))
        if signal_price is None or signal_date is None or current_date is None:
            continue
        elapsed_days = max(0, (current_date - signal_date).days)
        outcomes = entry.setdefault("outcomes", {})
        for horizon in horizons:
            key = f"{horizon}d"
            if elapsed_days >= horizon and key not in outcomes:
                outcomes[key] = {
                    "asof": current_date.isoformat(),
                    "return_pct": round((item.current_price / signal_price - 1.0) * 100.0, 2),
                    "stage": STAGE_LABELS[item.stage],
                }
                updated += 1

        trigger_price = _float_or_none(entry.get("trigger_price"))
        invalidation_price = _float_or_none(entry.get("invalidation_price"))
        if trigger_price is not None and item.current_price >= trigger_price and not entry.get("hit_trigger"):
            entry["hit_trigger"] = True
            entry["trigger_hit_date"] = current_date.isoformat()
            updated += 1
        if (
            invalidation_price is not None
            and item.current_price <= invalidation_price
            and not entry.get("hit_invalidation")
        ):
            entry["hit_invalidation"] = True
            entry["invalidation_hit_date"] = current_date.isoformat()
            entry["closed"] = True
            updated += 1
        if elapsed_days >= max(horizons):
            entry["closed"] = True
    return updated


def _write_markdown(path: Path, entries: list[dict[str, Any]]) -> None:
    lines = [
        "# 主题强趋势股决策日志",
        "",
        "| 日期 | 代码 | 名称 | 阶段 | 分数 | 触发 | 失效 | 1日 | 3日 | 5日 | 10日 | 状态 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for entry in reversed(entries[-100:]):
        outcomes = entry.get("outcomes", {})
        status = "失效" if entry.get("hit_invalidation") else "触发" if entry.get("hit_trigger") else "跟踪"
        lines.append(
            "| {date} | {code} | {name} | {stage} | {score} | {trigger} | {stop} | {r1} | {r3} | {r5} | {r10} | {status} |".format(
                date=entry.get("signal_date", "-"),
                code=entry.get("code", "-"),
                name=entry.get("name", "-") or "-",
                stage=entry.get("stage_label", "-"),
                score=_fmt(entry.get("score")),
                trigger=_fmt(entry.get("trigger_price")),
                stop=_fmt(entry.get("invalidation_price")),
                r1=_fmt_return(outcomes.get("1d")),
                r3=_fmt_return(outcomes.get("3d")),
                r5=_fmt_return(outcomes.get("5d")),
                r10=_fmt_return(outcomes.get("10d")),
                status=status,
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _write_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def _signal_id(item: ScanResult, latest_date: str) -> str:
    return f"{item.candidate.code}:{item.stage.value}:{latest_date}"


def _date_or_none(value: object) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: object) -> str:
    number = _float_or_none(value)
    if number is None:
        return "-"
    return f"{number:.2f}"


def _fmt_return(value: object) -> str:
    if not isinstance(value, dict):
        return "-"
    number = _float_or_none(value.get("return_pct"))
    if number is None:
        return "-"
    return f"{number:+.2f}%"
