# GitHub Actions 定时监控部署

这个项目支持用 GitHub Actions 定时扫描 `watch_list.xlsx`，并通过 Discord Webhook 推送监控看板。

## 1. 上传候选池

GitHub Actions 运行在云端，看不到本机的 `/Users/ethan/Documents/Codex/watch_list.xlsx`。

请把候选池放到仓库根目录：

```text
watch_list.xlsx
```

如果你的候选池仍维护在本机 `Documents/Codex/watch_list.xlsx`，可以在本地运行：

```bash
python scripts/sync_watchlist.py
```

它会复制一份到仓库根目录，之后再提交并推送到 GitHub。

建议保留这些列：

- `股票代码`
- `股票名称`
- `主题`
- `板块`
- `主题强度`

其中 `主题强度` 可填 0-100。没有该列也能跑，但主题强度会按保守分处理。

## 2. 配置 Discord Secret

进入 GitHub 仓库：

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

新增：

```text
Name: DISCORD_WEBHOOK_URL
Value: 你的 Discord Webhook URL
```

不要把 Webhook 写进代码、README 或 workflow。

## 3. 手动测试

进入：

`Actions` -> `Theme Second Wave Monitor` -> `Run workflow`

默认参数：

- `watchlist_path`: `watch_list.xlsx`
- `max_results`: `30`
- `send_discord`: `true`

首次建议先把 `send_discord` 设为 `false`，确认行情和看板生成正常后再打开推送。

## 4. 定时运行

当前 workflow 每个工作日北京时间 18:30 运行一次。

GitHub Actions 使用 UTC，所以 workflow 里对应的是：

```text
30 10 * * 1-5
```

## 5. 查看结果

每次运行后，可以在 Actions 运行详情页下载 artifact：

```text
theme-second-wave-dashboard
```

里面包含：

- `latest_dashboard.md`
- `latest_results.csv`
- `scan_*.md`

## 6. 常见问题

如果 workflow 在 `Ensure watchlist exists` 失败，说明仓库里没有 `watch_list.xlsx`，或手动运行时填写的路径不对。

如果 Discord 没收到消息，优先检查：

- 仓库 Secret 是否叫 `DISCORD_WEBHOOK_URL`
- Webhook 是否仍有效
- 手动运行时 `send_discord` 是否为 `true`
- Actions 日志里是否有 Discord 4xx/5xx 错误
