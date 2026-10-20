"""Interactive owner-only setup. No credentials accepted as command arguments."""

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path

from vault import Vault

ROOT = Path(__file__).resolve().parent


async def login(vault):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from transport import client_options

    with vault.locked():
        state = vault.load()
        print("API ID и API hash: https://my.telegram.org → API development tools")
        api_id = int(input("API ID: ").strip())
        api_hash = getpass.getpass("API hash (скрытый ввод): ").strip()
        if (
            api_id <= 0
            or len(api_hash) != 32
            or any(c not in "0123456789abcdefABCDEF" for c in api_hash)
        ):
            raise ValueError("Некорректные API ID / API hash.")
        client = TelegramClient(
            StringSession(state.get("session") or ""),
            api_id,
            api_hash,
            **client_options(),
        )
        try:
            await client.start(
                phone=lambda: input("Ваш номер Telegram с кодом страны: ").strip(),
                code_callback=lambda: getpass.getpass("Код Telegram (скрытый ввод): "),
                password=lambda: getpass.getpass("Пароль 2FA (скрытый ввод): "),
            )
            # Refuse bot sessions: this integration sends as the account owner.
            if (await client.get_me()).bot:
                raise ValueError("Требуется личный аккаунт, а не бот.")
            state["credentials"] = {"api_id": api_id, "api_hash": api_hash}
            state["session"] = client.session.save()
            vault.save(state)
            print(
                "Сессия сохранена через Windows DPAPI. Чаты пока не разрешены автоматически."
            )
        finally:
            await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Локальная настройка Telegram Local")
    parser.add_argument(
        "command",
        choices=["login", "file-root", "history-on", "history-off", "manifest"],
    )
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()
    vault = Vault(ROOT.parents[1] / "runtime" / "telegram-private")
    if args.command == "login":
        asyncio.run(login(vault))
    elif args.command == "manifest":
        config = {
            "mcpServers": {
                "telegram-local": {
                    "command": sys.executable,
                    "args": ["${PLUGIN_ROOT}/server.py"],
                    "env": {
                        "TELEGRAM_LOCAL_DATA": str(vault.directory),
                        "PYTHONIOENCODING": "utf-8",
                    },
                }
            }
        }
        (ROOT / ".mcp.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        print("Локальный MCP-манифест создан для текущего интерпретатора Python.")
    else:
        with vault.locked():
            state = vault.load()
            if args.command == "file-root":
                if not args.path:
                    parser.error(
                        "file-root требует абсолютную папку для исходящих файлов"
                    )
                path = Path(args.path)
                if not path.is_absolute() or not path.is_dir():
                    raise ValueError("Укажите существующую абсолютную папку.")
                resolved = path.resolve()
                if resolved == vault.directory or vault.directory in resolved.parents:
                    raise ValueError(
                        "Папка сессии не может быть папкой исходящих файлов."
                    )
                if str(resolved) not in state["file_roots"]:
                    state["file_roots"].append(str(resolved))
            else:
                enabled = args.command == "history-on"
                if (
                    enabled
                    and input(
                        "Разрешить чтение старой истории выбранных чатов? Введите ДА: "
                    )
                    != "ДА"
                ):
                    print("Настройка не изменена.")
                    return
                state["history_enabled"] = enabled
            vault.save(state)
            print("Настройка сохранена.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Настройка не завершена: {error}", file=sys.stderr)
        sys.exit(1)
