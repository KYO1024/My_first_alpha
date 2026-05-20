# 主题强趋势股二波/修复行情扫描器

这是一个轻量版交易战法项目，用来从 `watch_list.xlsx` 候选池中扫描“主题强趋势股二波/修复行情”机会。

当前版本先实现四件事：

- 读取候选池 Excel
- 拉取或载入日线行情
- 计算二波/修复评分和阶段判断
- 生成 Markdown 看板，并可选推送到 Discord Webhook

## 战法定义

本战法只做“主题强 + 个股强 + 一波后修复 + 二波触发”的结构。

核心阶段：

- `watch`: 主题或个股强度不足，暂不跟踪
- `first_wave`: 一波主升中，偏观察是否进入分歧
- `repair`: 一波后缩量回踩修复，等待二波触发
- `second_wave_confirmed`: 放量重新站上关键位或突破修复平台
- `failed`: 放量破位、跌破 MA20/MA60 或主题退潮

评分维度：

- 主题强度：候选池里填写的主题、板块、强度标签
- 一波强度：近期高点涨幅、放量突破、相对强势
- 修复质量：回撤幅度、缩量、守住 MA10/MA20
- 二波触发：站回 MA5/MA10、突破修复平台、放量确认
- 风险扣分：高位乖离、放量下跌、破位、数据不足

## 候选池格式

默认会按顺序查找：

1. `./watch_list.xlsx`
2. `./codex/watch_list.xlsx`
3. `/Users/ethan/.codex/watch_list.xlsx`
4. `~/Documents/Codex/watch_list.xlsx`
5. `~/codex/watch_list.xlsx`
6. `~/Documents/codex/watch_list.xlsx`

建议 Excel 至少包含一列股票代码。列名可用：

- 代码：`code`、`股票代码`、`证券代码`
- 名称：`name`、`股票名称`、`名称`
- 主题：`theme`、`主题`、`题材`
- 板块：`sector`、`板块`、`行业`
- 备注：`notes`、`备注`
- 主题强度：`theme_score`、`主题强度`

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

扫描候选池并生成看板：

```bash
python -m theme_second_wave.cli scan
```

指定候选池：

```bash
python -m theme_second_wave.cli scan --watchlist /path/to/watch_list.xlsx
```

使用本地 CSV 行情目录：

```bash
python -m theme_second_wave.cli scan --data-dir ./data/daily
```

CSV 文件名支持 `600519.csv`、`SH600519.csv`、`600519.SH.csv`，字段需要包含：

`date, open, high, low, close, volume`

## Discord 推送

复制配置：

```bash
cp .env.example .env
```

填入：

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

运行：

```bash
python -m theme_second_wave.cli scan --send-discord
```

## GitHub Actions 定时监控

如果要用 GitHub Actions 定时扫描并推送 Discord：

1. 把 `watch_list.xlsx` 放到仓库根目录
2. 在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中新增 `DISCORD_WEBHOOK_URL`
3. 到 `Actions -> Theme Second Wave Monitor` 手动运行一次

如果候选池还在本机 `Documents/Codex/watch_list.xlsx`，可先运行 `python scripts/sync_watchlist.py` 同步一份到仓库根目录。

详细步骤见 [docs/github-actions.md](docs/github-actions.md)。

## 输出

默认输出到：

```text
reports/latest_dashboard.md
reports/scan_YYYYMMDD_HHMMSS.md
reports/latest_results.csv
```

## 重要提醒

本项目只做研究和交易辅助，不构成投资建议。二波/修复模式的核心风险是“修复失败后补跌”，所以任何买入信号都必须配合失效价和仓位控制。
