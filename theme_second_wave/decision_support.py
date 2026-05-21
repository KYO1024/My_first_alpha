from __future__ import annotations

from .models import ScanResult, WaveStage


FOCUS_STAGES = {WaveStage.SECOND_WAVE_CONFIRMED, WaveStage.REPAIR, WaveStage.FIRST_WAVE}
STAGE_NAMES = {
    WaveStage.SECOND_WAVE_CONFIRMED: "二波确认",
    WaveStage.REPAIR: "分歧修复",
    WaveStage.FIRST_WAVE: "一波强势",
    WaveStage.FAILED: "结构失败",
    WaveStage.WATCH: "弱观察",
    WaveStage.DATA_MISSING: "数据不足",
}


def is_focus_signal(item: ScanResult) -> bool:
    return item.stage in FOCUS_STAGES and item.current_price is not None


def bull_case(item: ScanResult) -> str:
    if item.reasons:
        return "; ".join(item.reasons[:3])
    if item.stage in FOCUS_STAGES:
        return f"阶段处于{STAGE_NAMES[item.stage]}，仍在重点跟踪范围"
    return "暂无明确看多规则"


def bear_case(item: ScanResult) -> str:
    if item.risks:
        return "; ".join(item.risks[:3])
    if item.invalidation_price is not None:
        return f"若跌破失效价 {item.invalidation_price:.2f}，二波结构失效"
    return "暂无明确看空风险"


def risk_check(item: ScanResult) -> str:
    if item.stage == WaveStage.SECOND_WAVE_CONFIRMED:
        return "只按触发价和失效价执行，确认后仍需防范放量回落"
    if item.stage == WaveStage.REPAIR:
        return "等待放量突破，未触发前避免提前重仓"
    if item.stage == WaveStage.FIRST_WAVE:
        return "一波强势阶段不追高，等待分歧修复后的二波结构"
    if item.stage == WaveStage.FAILED:
        return "结构失败，剔除或仅保留复盘观察"
    if item.stage == WaveStage.DATA_MISSING:
        return "数据不足，不参与判断"
    return "弱观察，优先级低于修复和确认阶段"


def execution_condition(item: ScanResult) -> str:
    if item.stage == WaveStage.SECOND_WAVE_CONFIRMED:
        return _price_plan(item, "已确认，按计划执行")
    if item.stage == WaveStage.REPAIR:
        return _price_plan(item, "等待放量突破或站稳短均线")
    if item.stage == WaveStage.FIRST_WAVE:
        return _price_plan(item, "等待分歧修复后再评估触发")
    if item.stage == WaveStage.FAILED:
        return "不执行，除非重新进入候选池并修复结构"
    if item.stage == WaveStage.DATA_MISSING:
        return "不执行，等待行情数据恢复"
    return "不执行，仅观察结构是否改善"


def _price_plan(item: ScanResult, prefix: str) -> str:
    parts = [prefix]
    if item.trigger_price is not None:
        parts.append(f"触发 {item.trigger_price:.2f}")
    if item.invalidation_price is not None:
        parts.append(f"失效 {item.invalidation_price:.2f}")
    distance = item.metrics.get("trigger_distance_pct")
    if isinstance(distance, (int, float)):
        parts.append(f"距触发 {distance:+.2f}%")
    return " | ".join(parts)
