from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .models import ScanConfig
from .scanner import CandidateScanner


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main() -> None:
    _load_dotenv_if_available()
    parser = argparse.ArgumentParser(description="Theme second-wave repair scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="scan watch_list.xlsx")
    scan.add_argument("--watchlist", type=Path, default=None, help="path to watch_list.xlsx")
    scan.add_argument("--data-dir", type=Path, default=None, help="local OHLCV CSV directory")
    scan.add_argument("--report-dir", type=Path, default=Path("reports"), help="report output directory")
    scan.add_argument("--min-history-days", type=int, default=60)
    scan.add_argument("--max-results", type=int, default=30)
    scan.add_argument("--send-discord", action="store_true")
    scan.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "scan":
        config = ScanConfig(
            watchlist_path=args.watchlist,
            data_dir=args.data_dir,
            min_history_days=args.min_history_days,
            max_results=args.max_results,
            report_dir=args.report_dir,
            send_discord=args.send_discord,
        )
        scanner = CandidateScanner(config)
        results, report_path, csv_path = scanner.run_and_report()
        print(f"scanned {scanner.candidate_count} candidates")
        print(f"reported {len(results)} results")
        print(f"dashboard: {report_path}")
        print(f"csv: {csv_path}")
        if scanner.run_card_path is not None:
            print(f"run card: {scanner.run_card_path}")
        if scanner.decision_log_summary is not None:
            print(f"decision log: {scanner.decision_log_summary.jsonl_path}")
            print(f"decision markdown: {scanner.decision_log_summary.markdown_path}")


if __name__ == "__main__":
    main()
