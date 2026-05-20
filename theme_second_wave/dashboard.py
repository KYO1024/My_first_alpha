from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from .models import ScanResult, WaveStage


STAGE_LABELS = {
    WaveStage.SECOND_WAVE_CONFIRMED: "二波确认",
    WaveStage.REPAIR: "分歧修复",
    WaveStage.FIRST_WAVE: "一波强势",
    WaveStage.FAILED: "结构失败",
    WaveStage.WATCH: "弱观察",
    WaveStage.DATA_MISSING: "数据不足",
}


def sort_results(results: list[ScanResult]) -> list[ScanResult]:
    stage_rank = {
        WaveStage.SECOND_WAVE_CONFIRMED: 0,
        WaveStage.REPAIR: 1,
        WaveStage.FIRST_WAVE: 2,
        WaveStage.WATCH: 3,
        WaveStage.FAILED: 4,
        WaveStage.DATA_MISSING: 5,
    }
    return sorted(results, key=lambda r: (stage_rank[r.stage], -r.score, r.candidate.code))


def render_markdown(results: list[ScanResult], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now()
    ordered = sort_results(results)
    lines = [
        "# 主题强趋势股二波/修复行情看板",
        "",
        f"生成时间: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 总览",
        "",
        "| 阶段 | 数量 |",
        "|---|---:|",
    ]
    for stage in (
        WaveStage.SECOND_WAVE_CONFIRMED,
        WaveStage.REPAIR,
        WaveStage.FIRST_WAVE,
        WaveStage.WATCH,
        WaveStage.FAILED,
        WaveStage.DATA_MISSING,
    ):
        count = sum(1 for item in ordered if item.stage == stage)
        lines.append(f"| {STAGE_LABELS[stage]} | {count} |")

    lines.extend(
        [
            "",
            "## 候选明细",
            "",
            "| 排名 | 代码 | 名称 | 主题/板块 | 阶段 | 分数 | 现价 | 触发价 | 失效价 | 动作 |",
            "|---:|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for idx, item in enumerate(ordered, start=1):
        candidate = item.candidate
        theme = " / ".join(part for part in (candidate.theme, candidate.sector) if part) or "-"
        lines.append(
            "| {idx} | {code} | {name} | {theme} | {stage} | {score:.1f} | {price} | {trigger} | {stop} | {action} |".format(
                idx=idx,
                code=candidate.code,
                name=candidate.name or "-",
                theme=theme,
                stage=STAGE_LABELS[item.stage],
                score=item.score,
                price=_fmt(item.current_price),
                trigger=_fmt(item.trigger_price),
                stop=_fmt(item.invalidation_price),
                action=item.action,
            )
        )

    lines.extend(["", "## 重点跟踪", ""])
    focus = [
        item
        for item in ordered
        if item.stage in {WaveStage.SECOND_WAVE_CONFIRMED, WaveStage.REPAIR, WaveStage.FIRST_WAVE}
    ][:10]
    if not focus:
        lines.append("暂无达到重点跟踪标准的标的。")
    for item in focus:
        c = item.candidate
        lines.extend(
            [
                f"### {c.name or c.code} ({c.code})",
                "",
                f"- 阶段: {STAGE_LABELS[item.stage]}",
                f"- 分数: {item.score:.1f}",
                f"- 触发价: {_fmt(item.trigger_price)}",
                f"- 失效价: {_fmt(item.invalidation_price)}",
                f"- 高点回撤: {_fmt_pct(item.drawdown_from_high)}",
                f"- 修复量能: {_fmt(item.volume_contraction)} 倍一波高点附近均量",
                f"- 操作: {item.action}",
            ]
        )
        if item.reasons:
            lines.append(f"- 支持理由: {'; '.join(item.reasons[:4])}")
        if item.risks:
            lines.append(f"- 风险: {'; '.join(item.risks[:4])}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reports(results: list[ScanResult], report_dir: str | Path = "reports") -> tuple[Path, Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    markdown = render_markdown(results, now)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"scan_{timestamp}.md"
    latest_path = output_dir / "latest_dashboard.md"
    report_path.write_text(markdown, encoding="utf-8")
    latest_path.write_text(markdown, encoding="utf-8")
    csv_path = output_dir / "latest_results.csv"
    pd.DataFrame([to_row(item) for item in sort_results(results)]).to_csv(csv_path, index=False)
    return latest_path, csv_path


def to_row(item: ScanResult) -> dict[str, object]:
    candidate = item.candidate
    return {
        "code": candidate.code,
        "name": candidate.name,
        "theme": candidate.theme,
        "sector": candidate.sector,
        "stage": item.stage.value,
        "stage_label": STAGE_LABELS[item.stage],
        "score": item.score,
        "current_price": item.current_price,
        "trigger_price": item.trigger_price,
        "invalidation_price": item.invalidation_price,
        "drawdown_from_high": item.drawdown_from_high,
        "volume_contraction": item.volume_contraction,
        "bias_ma5": item.bias_ma5,
        "bias_ma20": item.bias_ma20,
        "action": item.action,
        "reasons": "; ".join(item.reasons),
        "risks": "; ".join(item.risks),
    }


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"
