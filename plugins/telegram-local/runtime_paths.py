"""Resolve per-user paths for the local Telegram plugin runtime and vault."""

import os
from pathlib import Path


def _codex_data_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("Telegram Local currently requires a Windows user profile.")
    return Path(local) / "Codex" / "TelegramLocal"


def user_data_dir() -> Path:
    configured = os.environ.get("TELEGRAM_LOCAL_DATA")
    return Path(configured).resolve() if configured else _codex_data_root() / "data"


def runtime_dir() -> Path:
    configured = os.environ.get("TELEGRAM_LOCAL_RUNTIME")
    return Path(configured).resolve() if configured else _codex_data_root() / "runtime"
