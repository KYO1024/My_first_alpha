# GitHub Actions 定时监控部署

这个项目支持用 GitHub Actions 定时扫描 `watch_list.xlsx`，也支持按 `config/sectors.yml` 自动拉取指定板块股票池，并通过 Discord Webhook 推送监控看板。

## 1. 上传候选池

如果使用手动候选池，GitHub Actions 运行在云端，看不到本机的 `/Users/ethan/Documents/Codex/watch_list.xlsx`。

请把候选池放到仓库根目录：

```text
watch_list.xlsx
```

如果你的候选池仍维护在本机 `Documents/Codex/watch_list.xlsx`，可以在本地运行：

```bash
python scripts/sync_watchlist.py
```

它会复制一份到仓库根目录，之后再提交并推送到 GitHub。

本地更新候选池后的推荐流程：

```bash
cd /Users/ethan/Documents/My_first_alpha
python scripts/sync_watchlist.py

git add watch_list.xlsx
git commit -m "Update watch list"
git -c http.proxy=http://127.0.0.1:7890 \
    -c http.version=HTTP/1.1 \
    push
```

然后到 GitHub Actions 手动运行 `Theme Second Wave Monitor`。

建议保留这些列：

- `股票代码`
- `股票名称`
- `主题`
- `板块`
- `主题强度`

其中 `主题强度` 可填 0-100。没有该列也能跑，但主题强度会按保守分处理。

## 2. 自动板块股票池

定时任务默认启用自动板块股票池，配置文件是：

```text
config/sectors.yml
```

每天北京时间 17:30，workflow 会先按配置拉取指定同花顺概念/行业成分股，生成：

```text
reports/auto_watch_list.xlsx
```

然后用这份股票池运行扫描并推送 Discord。

手动运行 workflow 时，可以把 `auto_watchlist` 设为 `false`，这时会跳过自动生成，直接使用 `watchlist_path` 指向的 Excel。

自动股票池支持：

- `type: concept`：同花顺概念板块
- `type: industry`：同花顺行业板块
- `exclude_st: true`：排除 ST
- `max_symbols_per_sector`：限制每个板块最多保留多少只
- `merge_manual_watchlist: true`：自动池与手动 `watch_list.xlsx` 合并去重

## 3. 配置 Discord Secret

进入 GitHub 仓库：

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

新增：

```text
Name: DISCORD_WEBHOOK_URL
Value: 你的 Discord Webhook URL
```

不要把 Webhook 写进代码、README 或 workflow。

## 4. 手动测试

进入：

`Actions` -> `Theme Second Wave Monitor` -> `Run workflow`

默认参数：

- `watchlist_path`: `watch_list.xlsx`
- `max_results`: `30`
- `send_discord`: `true`
- `auto_watchlist`: `false`

首次建议先把 `send_discord` 设为 `false`，确认行情和看板生成正常后再打开推送。

## 5. 定时运行

当前 workflow 每个工作日北京时间 17:30 运行一次。

GitHub Actions 使用 UTC，所以 workflow 里对应的是：

```text
30 9 * * 1-5
```

报告里的“生成时间”固定按 `Asia/Shanghai` 显示，避免 GitHub Actions 默认 UTC 时间造成 8 小时偏差。

## 6. 查看结果

每次运行后，可以在 Actions 运行详情页下载 artifact：

```text
theme-second-wave-dashboard
```

里面包含：

- `latest_dashboard.md`
- `latest_results.csv`
- `auto_watch_list.xlsx`
- `latest_run_card.json`
- `decision_log.jsonl`
- `decision_log.md`
- `scan_*.md`

## 7. 常见问题

如果 workflow 在 `Ensure watchlist exists` 失败，说明仓库里没有 `watch_list.xlsx`，或手动运行时填写的路径不对。自动板块模式下会跳过这个检查。

如果自动板块池生成失败，优先检查：

- `config/sectors.yml` 里的板块名称是否能被 akshare/同花顺接口识别
- `type` 是否为 `concept` 或 `industry`
- Actions 日志里是否有行情接口断开、限流或空数据

如果 Discord 没收到消息，优先检查：

- 仓库 Secret 是否叫 `DISCORD_WEBHOOK_URL`
- Webhook 是否仍有效
- 手动运行时 `send_discord` 是否为 `true`
- Actions 日志里是否有 Discord 4xx/5xx 错误
