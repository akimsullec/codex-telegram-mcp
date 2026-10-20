"""Short-lived, on-demand personal Telegram client; never prints credentials."""

import hashlib
from datetime import UTC, datetime

from telethon import TelegramClient, functions, types, utils
from telethon.sessions import StringSession


def client_options():
    return {
        "receive_updates": False,
        "catch_up": False,
        "request_retries": 0,
        "connection_retries": 1,
        "flood_sleep_threshold": 0,
        "device_model": "Telegram Local for Codex",
        "app_version": "0.1.1",
    }


def make_client(state):
    credentials = state.get("credentials")
    if not credentials or not state.get("session"):
        raise RuntimeError(
            "Аккаунт не подключён. Выполните локальную настройку setup.py login."
        )
    return TelegramClient(
        StringSession(state["session"]),
        credentials["api_id"],
        credentials["api_hash"],
        **client_options(),
    )


def describe(entity):
    peer = utils.get_input_peer(entity)
    if isinstance(peer, types.InputPeerUser):
        descriptor = {
            "kind": "user",
            "id": peer.user_id,
            "access_hash": peer.access_hash,
        }
    elif isinstance(peer, types.InputPeerChannel):
        descriptor = {
            "kind": "channel",
            "id": peer.channel_id,
            "access_hash": peer.access_hash,
        }
    elif isinstance(peer, types.InputPeerChat):
        descriptor = {"kind": "group", "id": peer.chat_id}
    else:
        raise TypeError("Этот тип чата не поддерживается.")
    return {
        "chat_id": utils.get_peer_id(peer),
        "title": utils.get_display_name(entity),
        "kind": descriptor["kind"],
        "peer": descriptor,
        "username": getattr(entity, "username", None),
    }


def input_peer(chat):
    peer = chat["peer"]
    if peer["kind"] == "user":
        return types.InputPeerUser(peer["id"], peer["access_hash"])
    if peer["kind"] == "channel":
        return types.InputPeerChannel(peer["id"], peer["access_hash"])
    return types.InputPeerChat(peer["id"])


class Transport:
    def __init__(self, client):
        self.client = client

    async def contacts(self, query):
        if len(query.strip()) < 2:
            raise ValueError(
                "Для поиска укажите минимум два символа имени или @username."
            )
        if query.startswith(("@", "https://t.me/")):
            entity = await self.client.get_entity(query)
            entities = [entity]
        else:
            contacts = await self.client(functions.contacts.GetContactsRequest(hash=0))
            entities = [
                u
                for u in contacts.users
                if query.casefold() in utils.get_display_name(u).casefold()
            ]
        return [
            {k: d[k] for k in ("chat_id", "title", "kind", "username")}
            for d in map(describe, entities)
        ][:25]

    async def resolve(self, reference):
        if reference.startswith(("@", "https://t.me/")):
            return describe(await self.client.get_entity(reference))
        if reference.lstrip("-").isdigit():
            numeric_id = int(reference)
            contacts = await self.client(functions.contacts.GetContactsRequest(hash=0))
            found = [u for u in contacts.users if u.id == numeric_id]
            if len(found) == 1:
                return describe(found[0])
            # Existing basic groups have no access hash; no joining is attempted.
            if numeric_id < 0 and not str(numeric_id).startswith("-100"):
                result = await self.client(
                    functions.messages.GetChatsRequest(id=[-numeric_id])
                )
                if len(result.chats) == 1:
                    return describe(result.chats[0])
            raise ValueError(
                "Не удалось однозначно разрешить ID. Укажите @username или ссылку существующего чата."
            )
        candidates = await self.contacts(reference)
        raise ValueError(
            "Сначала выберите точного получателя через find_chats; используйте его ID или @username. "
            f"Найдено кандидатов: {len(candidates)}."
        )

    async def send_text(self, chat, text, request_id):
        random_id = int.from_bytes(
            hashlib.sha256(request_id.encode()).digest()[:8], "big", signed=True
        )
        result = await self.client(
            functions.messages.SendMessageRequest(
                peer=input_peer(chat),
                message=text,
                random_id=random_id,
                no_webpage=True,
            )
        )
        message_id = getattr(result, "id", None)
        if message_id is None:
            message_id = next(
                (
                    u.id
                    for u in getattr(result, "updates", [])
                    if isinstance(u, types.UpdateMessageID) and u.random_id == random_id
                ),
                None,
            )
        return {
            "chat_id": chat["chat_id"],
            "message_id": message_id,
            "accepted_by_telegram": True,
        }

    async def send_file(self, chat, path, caption):
        # Force document preserves bytes/name; never reinterpret file bytes as markup.
        message = await self.client.send_file(
            input_peer(chat),
            str(path),
            caption=caption,
            parse_mode=None,
            force_document=True,
        )
        return {
            "chat_id": chat["chat_id"],
            "message_id": message.id,
            "accepted_by_telegram": True,
        }

    async def read(self, chat, cutoff, limit, before_id):
        rows, cursor, exhausted = [], before_id, False
        for _ in range(20):
            result = await self.client(
                functions.messages.SearchRequest(
                    peer=input_peer(chat),
                    q="",
                    filter=types.InputMessagesFilterEmpty(),
                    min_date=datetime.fromtimestamp(cutoff, UTC),
                    max_date=None,
                    offset_id=cursor,
                    add_offset=0,
                    limit=100,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )
            messages = [m for m in result.messages if isinstance(m, types.Message)]
            for message in messages:
                date = int(message.date.timestamp())
                if date < cutoff or message.out:
                    continue
                rows.append(
                    {
                        "id": message.id,
                        "date": date,
                        "text": message.message or "",
                        "sender_id": message.sender_id,
                        "outgoing": False,
                        "has_attachment": bool(message.media),
                    }
                )
            if len(rows) >= limit:
                return rows[:limit]
            if len(result.messages) < 100:
                exhausted = True
                break
            next_cursor = min(m.id for m in result.messages)
            if cursor and next_cursor >= cursor:
                raise RuntimeError(
                    "Telegram не продвинул страницу; чтение остановлено без изменения статуса сообщений."
                )
            cursor = next_cursor
        if not exhausted:
            raise RuntimeError(
                "Слишком много сообщений для одного запроса. Сузьте страницу через before_id."
            )
        return rows
