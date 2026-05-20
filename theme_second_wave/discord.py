from __future__ import annotations

import os


DISCORD_LIMIT = 1900


def send_discord_message(content: str, webhook_url: str | None = None) -> None:
    import requests

    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL is not configured")

    for chunk in _chunk(content, DISCORD_LIMIT):
        response = requests.post(url, json={"content": chunk}, timeout=20)
        response.raise_for_status()


def _chunk(content: str, limit: int) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in content.splitlines():
        addition = len(line) + 1
        if current and current_len + addition > limit:
            parts.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += addition
    if current:
        parts.append("\n".join(current))
    return parts or [content[:limit]]
