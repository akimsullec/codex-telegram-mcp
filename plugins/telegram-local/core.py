"""Policy boundary independent of Telegram/MCP; all message actions check it."""

import hashlib
import math
import time
import unicodedata
import uuid
from pathlib import Path


def key(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


class TelegramService:
    def __init__(self, state, save, transport, private_directory, clock=time.time):
        self.state, self.save, self.transport = state, save, transport
        self.private_directory = Path(private_directory).resolve()
        self.clock = clock

    def allowed(self, alias):
        chat = self.state["chats"].get(key(alias))
        if not chat:
            raise PermissionError(
                "Чат не разрешён. Сначала получите явное разрешение пользователя."
            )
        return chat

    def list_allowed(self):
        return [
            {k: c[k] for k in ("alias", "chat_id", "title", "kind", "allowed_at")}
            for c in self.state["chats"].values()
        ]

    async def allow_chat(self, reference, alias):
        if not key(alias) or len(alias) > 100:
            raise ValueError("Укажите короткий однозначный псевдоним чата.")
        # Resolve first, then bind the exact ID. Never silently rebind an alias.
        peer = await self.transport.resolve(reference)
        old = self.state["chats"].get(key(alias))
        if old:
            if old["chat_id"] != peer["chat_id"]:
                raise ValueError(
                    "Это имя уже привязано к другому чату. Сначала отзовите доступ."
                )
            return self.list_allowed()
        # A second alias cannot reset the date boundary for the same chat.
        existing = next(
            (
                c
                for c in self.state["chats"].values()
                if c["chat_id"] == peer["chat_id"]
            ),
            None,
        )
        allowed_at = existing["allowed_at"] if existing else math.ceil(self.clock())
        self.state["chats"][key(alias)] = dict(
            peer, alias=alias.strip(), allowed_at=allowed_at
        )
        self.save(self.state)
        return self.list_allowed()

    def revoke_chat(self, alias):
        chat_id = self.allowed(alias)["chat_id"]
        # Revoke every alias of that chat, not just its display name.
        self.state["chats"] = {
            k: c for k, c in self.state["chats"].items() if c["chat_id"] != chat_id
        }
        self.save(self.state)
        return {"revoked_chat_id": chat_id}

    def checked_file(self, path):
        candidate = Path(path)
        if not candidate.is_absolute():
            raise ValueError("Нужен абсолютный путь к файлу.")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("Путь не указывает на обычный файл.")
        if (
            resolved == self.private_directory
            or self.private_directory in resolved.parents
        ):
            raise PermissionError(
                "Файлы сессии и настроек плагина отправлять запрещено."
            )
        roots = [Path(root).resolve(strict=True) for root in self.state["file_roots"]]
        if not any(resolved.is_relative_to(root) for root in roots):
            raise PermissionError("Файл находится вне разрешённых локальных папок.")
        if resolved.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("В первой версии максимальный размер файла — 100 МиБ.")
        return resolved

    async def send(self, alias, request_id, text=None, path=None, caption=""):
        chat = self.allowed(alias)
        uuid.UUID(request_id)
        if (text is None) == (path is None):
            raise ValueError("Нужно указать либо текст, либо файл.")
        if text is not None and (
            not text.strip() or len(text.encode("utf-16-le")) // 2 > 4096
        ):
            raise ValueError("Текст должен содержать от 1 до 4096 UTF-16 единиц.")
        if len(caption.encode("utf-16-le")) // 2 > 1024:
            raise ValueError("Подпись к файлу слишком длинная.")
        content_hash = hashlib.sha256()
        checked = None
        if path is not None:
            checked = self.checked_file(path)
            with checked.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    content_hash.update(block)
        fingerprint = hashlib.sha256(
            repr(
                (chat["chat_id"], text, str(checked), content_hash.hexdigest(), caption)
            ).encode()
        ).hexdigest()
        previous = self.state["requests"].get(request_id)
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise ValueError("request_id уже использован для другого сообщения.")
            if previous["status"] == "sent":
                return dict(previous["result"], deduplicated=True)
            raise RuntimeError(
                "Исход прошлой отправки неизвестен. Не повторяйте её автоматически; проверьте Telegram."
            )
        # Persist before network access: crash/retry cannot silently resend a file.
        record = {
            "fingerprint": fingerprint,
            "status": "uncertain",
            "chat_id": chat["chat_id"],
        }
        self.state["requests"][request_id] = record
        self.save(self.state)
        if checked:
            result = await self.transport.send_file(chat, checked, caption)
        else:
            result = await self.transport.send_text(chat, text, request_id)
        record.update(status="sent", result=result)
        self.save(self.state)
        return dict(result, deduplicated=False)

    async def read(self, alias, limit=50, before_id=0, history=False):
        chat = self.allowed(alias)
        if not 1 <= limit <= 100 or before_id < 0:
            raise ValueError("limit: 1–100; before_id: неотрицательный ID.")
        if history and self.state["history_enabled"] is not True:
            raise PermissionError(
                "Чтение старой истории выключено. Включается пользователем в локальной настройке."
            )
        cutoff = 0 if history else chat["allowed_at"]
        # Transport receives a server-side date bound; double-check every returned row.
        rows = await self.transport.read(chat, cutoff, limit + 1, before_id)
        rows = [
            row for row in rows if row["date"] >= cutoff and not row.get("outgoing")
        ]
        rows.sort(key=lambda row: row["id"], reverse=True)
        page = rows[:limit]
        return {
            "chat": chat["alias"],
            "messages": page,
            "next_before_id": page[-1]["id"] if len(rows) > limit and page else None,
            "since": cutoff,
            "marks_as_read": False,
            "meaning_of_new": "Сообщения после разрешения чата; повторный запрос может вернуть те же сообщения.",
        }
