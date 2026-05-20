from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .models import StockCandidate


DEFAULT_WATCHLIST_PATHS = (
    Path("watch_list.xlsx"),
    Path("codex/watch_list.xlsx"),
    Path("/Users/ethan/.codex/watch_list.xlsx"),
    Path.home() / "Documents" / "Codex" / "watch_list.xlsx",
    Path.home() / "codex" / "watch_list.xlsx",
    Path.home() / "Documents" / "codex" / "watch_list.xlsx",
)

COLUMN_ALIASES = {
    "code": ("code", "stock_code", "symbol", "股票代码", "证券代码", "代码"),
    "name": ("name", "stock_name", "股票名称", "证券简称", "名称"),
    "theme": ("theme", "topic", "concept", "主题", "题材", "概念"),
    "sector": ("sector", "industry", "板块", "行业"),
    "notes": ("notes", "note", "备注", "说明"),
    "theme_score": ("theme_score", "主题强度", "题材强度", "strength"),
}


def resolve_watchlist_path(explicit_path: str | Path | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"watchlist not found: {path}")
        return path

    env_path = os.getenv("WATCHLIST_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"WATCHLIST_PATH not found: {path}")
        return path

    for path in DEFAULT_WATCHLIST_PATHS:
        expanded = path.expanduser()
        if expanded.exists():
            return expanded

    candidates = ", ".join(str(p) for p in DEFAULT_WATCHLIST_PATHS)
    raise FileNotFoundError(f"watch_list.xlsx not found. Checked: {candidates}")


def load_watchlist(path: str | Path | None = None) -> list[StockCandidate]:
    resolved = resolve_watchlist_path(path)
    df = pd.read_excel(resolved)
    df = df.dropna(how="all")
    if df.empty:
        return []

    normalized = {_normalize_column(col): col for col in df.columns}
    mapped = {
        key: _find_column(normalized, aliases)
        for key, aliases in COLUMN_ALIASES.items()
    }
    if mapped["code"] is None:
        raise ValueError("watchlist must include a stock code column")

    candidates: list[StockCandidate] = []
    seen: set[str] = set()
    for idx, row in df.iterrows():
        code = _string_value(row.get(mapped["code"]))
        if not code:
            continue
        code = normalize_code(code)
        if code in seen:
            continue
        seen.add(code)
        candidate = StockCandidate(
            code=code,
            name=_string_value(row.get(mapped["name"])) if mapped["name"] else "",
            theme=_string_value(row.get(mapped["theme"])) if mapped["theme"] else "",
            sector=_string_value(row.get(mapped["sector"])) if mapped["sector"] else "",
            notes=_string_value(row.get(mapped["notes"])) if mapped["notes"] else "",
            theme_score=_float_value(row.get(mapped["theme_score"])) if mapped["theme_score"] else None,
            source_row=int(idx) + 2,
        )
        candidates.append(candidate)

    return candidates


def normalize_code(value: str) -> str:
    text = str(value).strip().upper()
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def _normalize_column(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "")


def _find_column(normalized_columns: dict[str, object], aliases: tuple[str, ...]) -> object | None:
    for alias in aliases:
        key = _normalize_column(alias)
        if key in normalized_columns:
            return normalized_columns[key]
    return None


def _string_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _float_value(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
