from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .watchlist import load_watchlist, normalize_code


DEFAULT_SECTOR_CONFIG_PATH = Path("config/sectors.yml")
DEFAULT_AUTO_WATCHLIST_PATH = Path("reports/auto_watch_list.xlsx")


@dataclass(frozen=True)
class SectorSpec:
    type: str
    name: str
    theme_score: float | None = None
    max_symbols: int | None = None


@dataclass(frozen=True)
class AutoWatchlistConfig:
    enabled: bool
    max_symbols_per_sector: int
    exclude_st: bool
    merge_manual_watchlist: bool
    output_path: Path
    sectors: tuple[SectorSpec, ...]


def load_sector_config(path: str | Path = DEFAULT_SECTOR_CONFIG_PATH) -> AutoWatchlistConfig:
    config_path = Path(path)
    raw = _load_config(config_path)
    root = raw.get("auto_watchlist", raw)
    sectors = tuple(
        SectorSpec(
            type=str(item.get("type", "concept")),
            name=str(item["name"]),
            theme_score=_float_or_none(item.get("theme_score")),
            max_symbols=_int_or_none(item.get("max_symbols")),
        )
        for item in root.get("sectors", [])
        if item.get("name")
    )
    return AutoWatchlistConfig(
        enabled=_bool_value(root.get("enabled", True)),
        max_symbols_per_sector=int(root.get("max_symbols_per_sector", 80)),
        exclude_st=_bool_value(root.get("exclude_st", True)),
        merge_manual_watchlist=_bool_value(root.get("merge_manual_watchlist", True)),
        output_path=Path(root.get("output_path", DEFAULT_AUTO_WATCHLIST_PATH)),
        sectors=sectors,
    )


def build_auto_watchlist(
    *,
    config_path: str | Path = DEFAULT_SECTOR_CONFIG_PATH,
    output_path: str | Path | None = None,
    manual_watchlist_path: str | Path | None = None,
) -> Path:
    config = load_sector_config(config_path)
    if not config.enabled:
        raise ValueError("auto_watchlist is disabled in sector config")

    rows: list[dict[str, object]] = []
    for sector in config.sectors:
        members = fetch_sector_members(sector)
        if config.exclude_st:
            members = members[~members["name"].str.upper().str.contains("ST", na=False)]
        limit = sector.max_symbols or config.max_symbols_per_sector
        members = members.head(limit)
        for _, row in members.iterrows():
            rows.append(
                {
                    "股票代码": normalize_code(row["code"]),
                    "股票名称": str(row.get("name") or ""),
                    "主题": sector.name,
                    "行业": str(row.get("sector") or sector.name),
                    "主题强度": sector.theme_score,
                    "备注": f"auto:{sector.type}:{sector.name}",
                }
            )

    if config.merge_manual_watchlist and manual_watchlist_path:
        for candidate in load_watchlist(manual_watchlist_path):
            rows.append(
                {
                    "股票代码": candidate.code,
                    "股票名称": candidate.name,
                    "主题": candidate.theme,
                    "行业": candidate.sector,
                    "主题强度": candidate.theme_score,
                    "备注": candidate.notes or "manual",
                }
            )

    output = Path(output_path) if output_path is not None else config.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(_dedupe_rows(rows)).to_excel(output, index=False)
    return output


def fetch_sector_members(sector: SectorSpec) -> pd.DataFrame:
    if sector.type == "concept":
        return _fetch_concept_members(sector.name)
    if sector.type == "industry":
        return _fetch_industry_members(sector.name)
    raise ValueError(f"unsupported sector type: {sector.type}")


def _fetch_concept_members(name: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_board_concept_cons_ths(symbol=name)
    return _normalize_member_frame(raw, sector=name)


def _fetch_industry_members(name: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_board_industry_cons_ths(symbol=name)
    return _normalize_member_frame(raw, sector=name)


def _normalize_member_frame(raw: pd.DataFrame, sector: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise ValueError(f"sector returned empty members: {sector}")
    frame = raw.rename(
        columns={
            "代码": "code",
            "名称": "name",
            "股票代码": "code",
            "股票名称": "name",
            "证券代码": "code",
            "证券简称": "name",
        }
    )
    if "code" not in frame.columns or "name" not in frame.columns:
        raise ValueError(f"sector members missing code/name columns: {list(raw.columns)}")
    result = frame.loc[:, ["code", "name"]].copy()
    result["code"] = result["code"].map(normalize_code)
    result["name"] = result["name"].astype(str).str.strip()
    result["sector"] = sector
    result = result.dropna(subset=["code"]).drop_duplicates("code", keep="first")
    return result.reset_index(drop=True)


def _dedupe_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}
    for row in rows:
        code = normalize_code(str(row.get("股票代码", "")))
        if not code:
            continue
        if code in deduped:
            existing = deduped[code]
            existing["主题"] = _merge_text(existing.get("主题"), row.get("主题"))
            existing["行业"] = _merge_text(existing.get("行业"), row.get("行业"))
            existing["备注"] = _merge_text(existing.get("备注"), row.get("备注"))
            existing["主题强度"] = max(
                _float_or_none(existing.get("主题强度")) or 0.0,
                _float_or_none(row.get("主题强度")) or 0.0,
            )
            continue
        deduped[code] = {**row, "股票代码": code}
    return list(deduped.values())


def _load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.split("#", 1)[0].rstrip()
        if stripped:
            lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))

    root: dict[str, Any] = {}
    current_root: dict[str, Any] | None = None
    current_list_key: str | None = None
    current_item: dict[str, Any] | None = None
    for indent, line in lines:
        if indent == 0 and line.endswith(":"):
            key = line[:-1]
            root[key] = {}
            current_root = root[key]
            current_list_key = None
            current_item = None
            continue
        if current_root is None:
            key, value = _split_key_value(line)
            root[key] = _parse_scalar(value)
            continue
        if indent == 2 and line.endswith(":"):
            current_list_key = line[:-1]
            current_root[current_list_key] = []
            current_item = None
            continue
        if indent == 2:
            key, value = _split_key_value(line)
            current_root[key] = _parse_scalar(value)
            current_list_key = None
            current_item = None
            continue
        if indent == 4 and line.startswith("- "):
            if current_list_key is None:
                raise ValueError("invalid simple YAML list item")
            current_item = {}
            current_root[current_list_key].append(current_item)
            remainder = line[2:].strip()
            if remainder:
                key, value = _split_key_value(remainder)
                current_item[key] = _parse_scalar(value)
            continue
        if indent == 6 and current_item is not None:
            key, value = _split_key_value(line)
            current_item[key] = _parse_scalar(value)
            continue
        raise ValueError(f"unsupported config line: {line}")
    return root


def _split_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"invalid key/value line: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value == "":
        return {}
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip('"').strip("'")


def _merge_text(left: object, right: object) -> str:
    parts = []
    for value in (left, right):
        for part in str(value or "").split(" / "):
            text = part.strip()
            if text and text not in parts:
                parts.append(text)
    return " / ".join(parts)


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
