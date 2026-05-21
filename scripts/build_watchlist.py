from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_second_wave.sector_watchlist import build_auto_watchlist


def main() -> None:
    parser = argparse.ArgumentParser(description="Build watch_list.xlsx from sector config")
    parser.add_argument("--config", type=Path, default=Path("config/sectors.yml"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--manual-watchlist", type=Path, default=Path("watch_list.xlsx"))
    args = parser.parse_args()

    output = build_auto_watchlist(
        config_path=args.config,
        output_path=args.output,
        manual_watchlist_path=args.manual_watchlist if args.manual_watchlist.exists() else None,
    )
    print(f"auto watchlist: {output}")


if __name__ == "__main__":
    main()
