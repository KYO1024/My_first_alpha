from __future__ import annotations

import math

import pandas as pd

from .indicators import add_indicators, safe_pct
from .models import ScanResult, ScoreBreakdown, StockCandidate, WaveStage


class ThemeSecondWaveAnalyzer:
    def __init__(self, min_history_days: int = 60):
        self.min_history_days = min_history_days

    def analyze(self, candidate: StockCandidate, daily_bars: pd.DataFrame) -> ScanResult:
        data_source = str(daily_bars.attrs.get("source", "unknown"))
        try:
            df = add_indicators(daily_bars)
        except Exception as exc:
            return self._missing(candidate, f"行情字段无法标准化: {exc}")

        if len(df) < self.min_history_days:
            return self._missing(candidate, f"历史数据不足: {len(df)} < {self.min_history_days}")

        latest = df.iloc[-1]
        current = float(latest["close"])
        ma5 = _num(latest.get("ma5"))
        ma10 = _num(latest.get("ma10"))
        ma20 = _num(latest.get("ma20"))
        ma60 = _num(latest.get("ma60"))

        pivot_slice = df.tail(60).copy()
        pivot_idx = pivot_slice["high"].idxmax()
        pivot_row = df.loc[pivot_idx]
        pivot_high = float(pivot_row["high"])
        before_pivot = df.loc[max(0, pivot_idx - 30) : pivot_idx]
        base_low = float(before_pivot["low"].min())
        first_wave_gain = safe_pct(pivot_high, base_low)
        bars_since_high = len(df) - 1 - int(pivot_idx)
        drawdown = safe_pct(current, pivot_high)

        repair_window = df.tail(max(5, min(20, bars_since_high if bars_since_high > 0 else 5)))
        prior_volume = df.loc[max(0, pivot_idx - 10) : pivot_idx, "volume"].mean()
        repair_volume = repair_window["volume"].mean()
        volume_contraction = repair_volume / prior_volume if prior_volume and prior_volume > 0 else math.nan

        bias_ma5 = safe_pct(current, ma5) if ma5 else None
        bias_ma20 = safe_pct(current, ma20) if ma20 else None
        repair_high = float(repair_window["high"].max())
        repair_low = float(repair_window["low"].min())
        recent_volume_ratio = (
            float(latest["volume"]) / float(latest["vol_ma5"])
            if _num(latest.get("vol_ma5"))
            else math.nan
        )

        breakdown = ScoreBreakdown()
        reasons: list[str] = []
        risks: list[str] = []

        self._score_theme(candidate, breakdown, reasons, risks)
        self._score_first_wave(first_wave_gain, pivot_high, current, breakdown, reasons, risks)
        self._score_repair(
            current=current,
            ma10=ma10,
            ma20=ma20,
            ma60=ma60,
            drawdown=drawdown,
            bars_since_high=bars_since_high,
            volume_contraction=volume_contraction,
            breakdown=breakdown,
            reasons=reasons,
            risks=risks,
        )
        self._score_trigger(
            current=current,
            ma5=ma5,
            ma10=ma10,
            repair_high=repair_high,
            recent_volume_ratio=recent_volume_ratio,
            breakdown=breakdown,
            reasons=reasons,
        )
        self._score_risk(
            current=current,
            ma20=ma20,
            ma60=ma60,
            bias_ma5=bias_ma5,
            latest_pct_chg=_num(latest.get("pct_chg")),
            recent_volume_ratio=recent_volume_ratio,
            breakdown=breakdown,
            risks=risks,
        )

        stage = self._classify_stage(
            score=breakdown.total,
            first_wave_gain=first_wave_gain,
            bars_since_high=bars_since_high,
            drawdown=drawdown,
            current=current,
            ma5=ma5,
            ma10=ma10,
            ma20=ma20,
            repair_high=repair_high,
            recent_volume_ratio=recent_volume_ratio,
        )

        trigger_price = max(x for x in (ma5, ma10, repair_high) if x)
        invalidation_candidates = [x for x in (ma20, ma60, repair_low) if x]
        invalidation = max(min(invalidation_candidates), 0.0) if invalidation_candidates else None
        trigger_distance = safe_pct(trigger_price, current) if trigger_price else None
        latest_date = pd.to_datetime(latest["date"]).strftime("%Y-%m-%d")

        return ScanResult(
            candidate=candidate,
            stage=stage,
            score=round(breakdown.total, 1),
            breakdown=breakdown,
            current_price=current,
            trigger_price=round(trigger_price, 3) if trigger_price else None,
            invalidation_price=round(invalidation, 3) if invalidation else None,
            pivot_high=round(pivot_high, 3),
            drawdown_from_high=round(drawdown, 2),
            volume_contraction=round(volume_contraction, 2) if not math.isnan(volume_contraction) else None,
            bias_ma5=round(bias_ma5, 2) if bias_ma5 is not None else None,
            bias_ma20=round(bias_ma20, 2) if bias_ma20 is not None else None,
            reasons=reasons,
            risks=risks,
            metrics={
                "first_wave_gain": round(first_wave_gain, 2),
                "bars_since_high": bars_since_high,
                "repair_high": round(repair_high, 3),
                "repair_low": round(repair_low, 3),
                "recent_volume_ratio": round(recent_volume_ratio, 2)
                if not math.isnan(recent_volume_ratio)
                else None,
                "ma5": round(ma5, 3) if ma5 else None,
                "ma10": round(ma10, 3) if ma10 else None,
                "ma20": round(ma20, 3) if ma20 else None,
                "ma60": round(ma60, 3) if ma60 else None,
                "trigger_distance_pct": round(trigger_distance, 2)
                if trigger_distance is not None
                else None,
                "latest_date": latest_date,
                "data_source": data_source,
            },
        )

    def _score_theme(
        self,
        candidate: StockCandidate,
        breakdown: ScoreBreakdown,
        reasons: list[str],
        risks: list[str],
    ) -> None:
        score = candidate.theme_score if candidate.theme_score is not None else None
        if score is not None:
            normalized = score if score <= 20 else score / 5
            breakdown.theme_strength += max(0.0, min(20.0, normalized))
            reasons.append(f"候选池主题强度: {score:g}")
        elif candidate.theme or candidate.sector:
            breakdown.theme_strength += 12
            reasons.append("候选池已标注主题/板块")
        else:
            breakdown.theme_strength += 6
            risks.append("候选池未标注主题，主题强度需要人工确认")

    def _score_first_wave(
        self,
        first_wave_gain: float,
        pivot_high: float,
        current: float,
        breakdown: ScoreBreakdown,
        reasons: list[str],
        risks: list[str],
    ) -> None:
        if first_wave_gain >= 45:
            breakdown.first_wave_quality += 20
            reasons.append(f"一波涨幅强: {first_wave_gain:.1f}%")
        elif first_wave_gain >= 25:
            breakdown.first_wave_quality += 15
            reasons.append(f"一波涨幅合格: {first_wave_gain:.1f}%")
        elif first_wave_gain >= 12:
            breakdown.first_wave_quality += 9
            risks.append(f"一波强度一般: {first_wave_gain:.1f}%")
        else:
            breakdown.first_wave_quality += 3
            risks.append(f"缺少明确一波主升: {first_wave_gain:.1f}%")

        if current >= pivot_high * 0.92:
            breakdown.first_wave_quality += 3
            reasons.append("价格仍接近一波高点区")

    def _score_repair(
        self,
        *,
        current: float,
        ma10: float | None,
        ma20: float | None,
        ma60: float | None,
        drawdown: float,
        bars_since_high: int,
        volume_contraction: float,
        breakdown: ScoreBreakdown,
        reasons: list[str],
        risks: list[str],
    ) -> None:
        if 3 <= bars_since_high <= 25:
            breakdown.repair_quality += 5
            reasons.append(f"高点后修复天数合适: {bars_since_high} 天")
        elif bars_since_high < 3:
            risks.append("刚创新高，尚未充分分歧修复")
        else:
            risks.append(f"高点后时间偏长: {bars_since_high} 天")

        if -18 <= drawdown <= -4:
            breakdown.repair_quality += 7
            reasons.append(f"回撤幅度健康: {drawdown:.1f}%")
        elif -28 <= drawdown < -18:
            breakdown.repair_quality += 3
            risks.append(f"回撤偏深: {drawdown:.1f}%")
        elif drawdown > -4:
            breakdown.repair_quality += 2
            risks.append("回撤不充分，容易高位震荡")
        else:
            risks.append(f"回撤过深，二波难度上升: {drawdown:.1f}%")

        if not math.isnan(volume_contraction) and volume_contraction <= 0.65:
            breakdown.repair_quality += 8
            reasons.append(f"修复期明显缩量: {volume_contraction:.2f} 倍")
        elif not math.isnan(volume_contraction) and volume_contraction <= 0.85:
            breakdown.repair_quality += 5
            reasons.append(f"修复期温和缩量: {volume_contraction:.2f} 倍")
        else:
            risks.append("修复期未见明显缩量")

        if ma20 and current >= ma20:
            breakdown.repair_quality += 5
            reasons.append("价格守住 MA20")
        elif ma60 and current >= ma60:
            breakdown.repair_quality += 2
            risks.append("跌破 MA20，仅靠 MA60 支撑")
        else:
            risks.append("关键均线支撑不足")

        if ma10 and current >= ma10:
            breakdown.repair_quality += 3
            reasons.append("价格站在 MA10 上方")

    def _score_trigger(
        self,
        *,
        current: float,
        ma5: float | None,
        ma10: float | None,
        repair_high: float,
        recent_volume_ratio: float,
        breakdown: ScoreBreakdown,
        reasons: list[str],
    ) -> None:
        if ma5 and current >= ma5:
            breakdown.trigger_quality += 4
            reasons.append("重新站上 MA5")
        if ma10 and current >= ma10:
            breakdown.trigger_quality += 4
            reasons.append("重新站上 MA10")
        if current >= repair_high * 0.995:
            breakdown.trigger_quality += 5
            reasons.append("接近或突破修复平台高点")
        if not math.isnan(recent_volume_ratio) and recent_volume_ratio >= 1.25:
            breakdown.trigger_quality += 7
            reasons.append(f"放量确认: {recent_volume_ratio:.2f} 倍 5 日均量")

    def _score_risk(
        self,
        *,
        current: float,
        ma20: float | None,
        ma60: float | None,
        bias_ma5: float | None,
        latest_pct_chg: float | None,
        recent_volume_ratio: float,
        breakdown: ScoreBreakdown,
        risks: list[str],
    ) -> None:
        if bias_ma5 is not None and bias_ma5 > 8:
            breakdown.risk_penalty += 8
            risks.append(f"MA5 乖离偏高: {bias_ma5:.1f}%")
        if ma20 and current < ma20:
            breakdown.risk_penalty += 12
            risks.append("跌破 MA20")
        if ma60 and current < ma60:
            breakdown.risk_penalty += 8
            risks.append("跌破 MA60")
        if (
            latest_pct_chg is not None
            and latest_pct_chg < -4
            and not math.isnan(recent_volume_ratio)
            and recent_volume_ratio > 1.2
        ):
            breakdown.risk_penalty += 10
            risks.append("放量下跌，修复失败风险上升")

    def _classify_stage(
        self,
        *,
        score: float,
        first_wave_gain: float,
        bars_since_high: int,
        drawdown: float,
        current: float,
        ma5: float | None,
        ma10: float | None,
        ma20: float | None,
        repair_high: float,
        recent_volume_ratio: float,
    ) -> WaveStage:
        if ma20 and current < ma20 * 0.97:
            return WaveStage.FAILED
        if first_wave_gain < 12:
            return WaveStage.WATCH
        triggered = (
            ma5
            and ma10
            and current >= ma5
            and current >= ma10
            and current >= repair_high * 0.995
            and not math.isnan(recent_volume_ratio)
            and recent_volume_ratio >= 1.15
        )
        if score >= 72 and triggered:
            return WaveStage.SECOND_WAVE_CONFIRMED
        if 3 <= bars_since_high <= 25 and -28 <= drawdown <= -4 and score >= 52:
            return WaveStage.REPAIR
        if bars_since_high <= 5 and first_wave_gain >= 25:
            return WaveStage.FIRST_WAVE
        return WaveStage.WATCH

    def _missing(self, candidate: StockCandidate, reason: str) -> ScanResult:
        return ScanResult(
            candidate=candidate,
            stage=WaveStage.DATA_MISSING,
            score=0.0,
            breakdown=ScoreBreakdown(),
            risks=[reason],
        )


def _num(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric
