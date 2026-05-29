from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from theme_second_wave import sector_watchlist
from theme_second_wave.sector_watchlist import (
    SectorSpec,
    build_auto_watchlist,
    load_sector_config,
)


def test_load_sector_config_from_simple_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "sectors.yml"
    config_path.write_text(
        """
auto_watchlist:
  enabled: true
  max_symbols_per_sector: 2
  exclude_st: true
  merge_manual_watchlist: false
  output_path: reports/auto_watch_list.xlsx
  sectors:
    - type: concept
      name: 数据中心
      theme_score: 80
""".strip(),
        encoding="utf-8",
    )

    config = load_sector_config(config_path)

    assert config.enabled is True
    assert config.max_symbols_per_sector == 2
    assert config.merge_manual_watchlist is False
    assert config.sectors == (SectorSpec(type="concept", name="数据中心", theme_score=80.0),)


def test_build_auto_watchlist_merges_manual_and_dedupes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "sectors.yml"
    output_path = tmp_path / "auto.xlsx"
    manual_path = tmp_path / "manual.xlsx"
    config_path.write_text(
        """
auto_watchlist:
  enabled: true
  max_symbols_per_sector: 3
  exclude_st: true
  merge_manual_watchlist: true
  output_path: auto.xlsx
  sectors:
    - type: concept
      name: 数据中心
      theme_score: 80
""".strip(),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"股票代码": "603881", "股票名称": "数据港", "主题": "数据中心", "行业": "IDC"},
            {"股票代码": "300000", "股票名称": "手动股", "主题": "手动主题", "行业": "手动行业"},
        ]
    ).to_excel(manual_path, index=False)

    def fake_fetch(sector: SectorSpec) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"code": "603881", "name": "数据港", "sector": sector.name},
                {"code": "000001", "name": "ST测试", "sector": sector.name},
                {"code": "688313", "name": "仕佳光子", "sector": sector.name},
            ]
        )

    monkeypatch.setattr(sector_watchlist, "fetch_sector_members", fake_fetch)

    output = build_auto_watchlist(
        config_path=config_path,
        output_path=output_path,
        manual_watchlist_path=manual_path,
    )
    df = pd.read_excel(output)

    assert output == output_path
    assert df["股票代码"].astype(str).str.zfill(6).tolist() == ["603881", "688313", "300000"]
    merged = df[df["股票代码"].astype(str).str.zfill(6) == "603881"].iloc[0]
    assert "数据中心" in merged["主题"]
    assert "IDC" in merged["行业"]
    assert merged["主题强度"] == 80


def test_fetch_members_falls_back_when_ths_function_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ak = SimpleNamespace(
        stock_board_concept_cons_em=lambda symbol: pd.DataFrame(
            [{"代码": "603881", "名称": "数据港"}]
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    result = sector_watchlist._fetch_concept_members("数据中心")

    assert result.to_dict("records") == [{"code": "603881", "name": "数据港", "sector": "数据中心"}]


def test_build_auto_watchlist_skips_failed_sector_and_uses_manual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "sectors.yml"
    output_path = tmp_path / "auto.xlsx"
    manual_path = tmp_path / "manual.xlsx"
    config_path.write_text(
        """
auto_watchlist:
  enabled: true
  max_symbols_per_sector: 3
  exclude_st: true
  merge_manual_watchlist: true
  output_path: auto.xlsx
  sectors:
    - type: concept
      name: 不存在板块
      theme_score: 80
""".strip(),
        encoding="utf-8",
    )
    pd.DataFrame(
        [{"股票代码": "300000", "股票名称": "手动股", "主题": "手动主题", "行业": "手动行业"}]
    ).to_excel(manual_path, index=False)

    def fail_fetch(sector: SectorSpec) -> pd.DataFrame:
        raise RuntimeError("remote sector api failed")

    monkeypatch.setattr(sector_watchlist, "fetch_sector_members", fail_fetch)

    output = build_auto_watchlist(
        config_path=config_path,
        output_path=output_path,
        manual_watchlist_path=manual_path,
    )
    df = pd.read_excel(output)

    assert df["股票代码"].astype(str).str.zfill(6).tolist() == ["300000"]
