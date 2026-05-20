from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_second_wave.watchlist import resolve_watchlist_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local watch_list.xlsx into repo root")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--target", type=Path, default=Path("watch_list.xlsx"))
    args = parser.parse_args()

    source = resolve_watchlist_path(args.source)
    target = args.target
    if source.resolve() == target.resolve():
        print(f"watchlist already in place: {target}")
        return

    shutil.copy2(source, target)
    print(f"copied {source} -> {target}")


if __name__ == "__main__":
    main()
