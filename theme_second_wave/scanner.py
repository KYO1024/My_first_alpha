from __future__ import annotations

import logging
from pathlib import Path

from .dashboard import render_discord_summary, sort_results, write_reports
from .discord import send_discord_message
from .market_data import MarketDataProvider
from .models import ScanConfig, ScanResult
from .strategy import ThemeSecondWaveAnalyzer
from .watchlist import load_watchlist

logger = logging.getLogger(__name__)


class CandidateScanner:
    def __init__(self, config: ScanConfig):
        self.config = config
        self.data_provider = MarketDataProvider(config.data_dir)
        self.analyzer = ThemeSecondWaveAnalyzer(config.min_history_days)

    def run(self) -> list[ScanResult]:
        candidates = load_watchlist(self.config.watchlist_path)
        results: list[ScanResult] = []
        for candidate in candidates:
            try:
                bars = self.data_provider.get_daily(candidate.code, days=140)
                result = self.analyzer.analyze(candidate, bars)
            except Exception as exc:
                logger.warning("scan failed for %s: %s", candidate.code, exc)
                result = self.analyzer._missing(candidate, str(exc))
            results.append(result)
        return sort_results(results)[: self.config.max_results]

    def run_and_report(self) -> tuple[list[ScanResult], Path, Path]:
        results = self.run()
        markdown_path, csv_path = write_reports(results, self.config.report_dir)
        if self.config.send_discord:
            send_discord_message(_discord_summary(render_discord_summary(results)))
        return results, markdown_path, csv_path


def _discord_summary(markdown: str) -> str:
    lines = markdown.splitlines()
    keep: list[str] = []
    for line in lines:
        keep.append(line)
        if len("\n".join(keep)) > 4500:
            keep.append("")
            keep.append("完整看板请查看本地 reports/latest_dashboard.md")
            break
    return "\n".join(keep)
