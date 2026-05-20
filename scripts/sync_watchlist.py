from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme_second_wave.watchlist import DEFAULT_WATCHLIST_PATHS, resolve_watchlist_path


def resolve_sync_source(explicit_source: Path | None, target: Path) -> Path:
    if explicit_source is not None:
        return resolve_watchlist_path(explicit_source)

    env_path = os.getenv("WATCHLIST_PATH")
    if env_path:
        return resolve_watchlist_path(env_path)

    target_path = target.expanduser().resolve()
    for path in DEFAULT_WATCHLIST_PATHS:
        candidate = path.expanduser()
        if candidate.exists() and candidate.resolve() != target_path:
            return candidate

    return resolve_watchlist_path(None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local watch_list.xlsx into repo root")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--target", type=Path, default=Path("watch_list.xlsx"))
    args = parser.parse_args()

    source = resolve_sync_source(args.source, args.target)
    target = args.target
    if source.resolve() == target.resolve():
        print(f"watchlist already in place: {target}")
        return

    shutil.copy2(source, target)
    print(f"copied {source} -> {target}")


if __name__ == "__main__":
    main()
