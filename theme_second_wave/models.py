from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class WaveStage(str, Enum):
    WATCH = "watch"
    FIRST_WAVE = "first_wave"
    REPAIR = "repair"
    SECOND_WAVE_CONFIRMED = "second_wave_confirmed"
    FAILED = "failed"
    DATA_MISSING = "data_missing"


@dataclass(frozen=True)
class StockCandidate:
    code: str
    name: str = ""
    theme: str = ""
    sector: str = ""
    notes: str = ""
    theme_score: float | None = None
    source_row: int | None = None


@dataclass
class ScoreBreakdown:
    theme_strength: float = 0.0
    first_wave_quality: float = 0.0
    repair_quality: float = 0.0
    trigger_quality: float = 0.0
    risk_penalty: float = 0.0

    @property
    def total(self) -> float:
        raw = (
            self.theme_strength
            + self.first_wave_quality
            + self.repair_quality
            + self.trigger_quality
            - self.risk_penalty
        )
        return max(0.0, min(100.0, raw))


@dataclass
class ScanResult:
    candidate: StockCandidate
    stage: WaveStage
    score: float
    breakdown: ScoreBreakdown
    current_price: float | None = None
    trigger_price: float | None = None
    invalidation_price: float | None = None
    pivot_high: float | None = None
    drawdown_from_high: float | None = None
    volume_contraction: float | None = None
    bias_ma5: float | None = None
    bias_ma20: float | None = None
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        if self.stage == WaveStage.SECOND_WAVE_CONFIRMED:
            return "确认二波，按触发价和失效价执行"
        if self.stage == WaveStage.REPAIR:
            return "修复观察，等待放量突破或站稳短均线"
        if self.stage == WaveStage.FIRST_WAVE:
            return "一波强势中，等待分歧修复"
        if self.stage == WaveStage.FAILED:
            return "结构失败，剔除或降级观察"
        if self.stage == WaveStage.DATA_MISSING:
            return "数据不足，无法判断"
        return "弱观察"


@dataclass(frozen=True)
class ScanConfig:
    watchlist_path: Path | None = None
    data_dir: Path | None = None
    min_history_days: int = 60
    max_results: int = 30
    report_dir: Path = Path("reports")
    send_discord: bool = False
