from __future__ import annotations

import json
import os
import sys
import urllib.request
from getpass import getpass
from pathlib import Path


def _resolve_webhook() -> str:
    env_value = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if env_value:
        return env_value

    dotenv_value = _read_dotenv_value("DISCORD_WEBHOOK_URL")
    if dotenv_value:
        return dotenv_value

    if sys.stdin.isatty():
        return getpass("Discord webhook URL: ").strip()
    return sys.stdin.readline().strip()


def _read_dotenv_value(key: str, path: str | Path = ".env") -> str:
    dotenv = Path(path)
    if not dotenv.exists():
        return ""
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip().strip('"').strip("'")
        return value
    return ""


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: push_discord.py <markdown-file>")

    webhook = _resolve_webhook()
    if not webhook:
        raise SystemExit(
            "Discord webhook URL is required. Set DISCORD_WEBHOOK_URL in .env "
            "or pass it on stdin."
        )

    markdown_path = Path(sys.argv[1])
    text = markdown_path.read_text(encoding="utf-8")
    content = "主题二波/修复监控结果\n\n" + text
    chunks = _chunk(content, 1800)
    for index, chunk in enumerate(chunks, start=1):
        payload = json.dumps({"content": chunk}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            webhook,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "theme-second-wave-scanner/0.1",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"sent chunk {index}/{len(chunks)} status={response.status}")


def _chunk(content: str, limit: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in content.splitlines():
        addition = len(line) + 1
        if current and current_len + addition > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += addition
    if current:
        chunks.append("\n".join(current))
    return chunks


if __name__ == "__main__":
    main()
