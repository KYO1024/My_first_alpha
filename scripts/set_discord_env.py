from __future__ import annotations

from getpass import getpass
from pathlib import Path


def main() -> None:
    url = getpass("Discord webhook URL: ").strip()
    if not url.startswith("https://discord.com/api/webhooks/"):
        raise SystemExit("Invalid Discord webhook URL")

    path = Path(".env")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    output: list[str] = []
    updated = False
    for line in lines:
        if line.strip().startswith("DISCORD_WEBHOOK_URL="):
            output.append(f"DISCORD_WEBHOOK_URL={url}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(f"DISCORD_WEBHOOK_URL={url}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    path.chmod(0o600)
    print("wrote .env with DISCORD_WEBHOOK_URL")


if __name__ == "__main__":
    main()
