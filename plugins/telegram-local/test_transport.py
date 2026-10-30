import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from telethon import types
from transport import Transport, input_peer


class FakeClient:
    def __init__(self, result):
        self.calls = []
        self.result = result

    async def __call__(self, request):
        self.calls.append(request)
        return self.result


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_date_bound_and_peer_applied_to_real_request_schema(self):
        messages = [
            types.Message(
                id=7,
                peer_id=types.PeerUser(123),
                date=datetime.fromtimestamp(102, UTC),
                message="synthetic",
            ),
            types.Message(
                id=6,
                peer_id=types.PeerUser(123),
                date=datetime.fromtimestamp(99, UTC),
                message="old",
            ),
        ]
        client = FakeClient(SimpleNamespace(messages=messages))
        transport = Transport(client)
        chat = {"chat_id": 123, "peer": {"kind": "user", "id": 123, "access_hash": 456}}
        rows = await transport.read(chat, cutoff=101, limit=2, before_id=10)
        self.assertEqual([r["id"] for r in rows], [7])
        request = client.calls[0]
        self.assertEqual(request.peer.user_id, 123)
        self.assertEqual(int(request.min_date.timestamp()), 101)
        self.assertEqual(request.offset_id, 10)

    async def test_text_retry_reuses_random_id_and_plain_text(self):
        client = FakeClient(
            types.UpdateShortSentMessage(
                id=10, pts=1, pts_count=1, date=datetime.now(UTC), out=True
            )
        )
        transport = Transport(client)
        chat = {"chat_id": 123, "peer": {"kind": "user", "id": 123, "access_hash": 456}}
        for _ in range(2):
            result = await transport.send_text(chat, "<b>plain</b>", "synthetic-id")
        self.assertEqual(result["message_id"], 10)
        self.assertEqual(client.calls[0].random_id, client.calls[1].random_id)
        self.assertIsNone(client.calls[0].entities)

    async def test_ambiguous_display_name_never_selects(self):
        users = [
            types.User(id=1, first_name="Test", access_hash=1),
            types.User(id=2, first_name="Test", access_hash=2),
        ]
        transport = Transport(FakeClient(SimpleNamespace(users=users)))
        self.assertEqual(len(await transport.contacts("Test")), 2)
        with self.assertRaises(ValueError):
            await transport.resolve("Test")

    async def test_peer_variants(self):
        self.assertEqual(input_peer({"peer": {"kind": "group", "id": 4}}).chat_id, 4)
        self.assertEqual(
            input_peer(
                {"peer": {"kind": "channel", "id": 5, "access_hash": 6}}
            ).channel_id,
            5,
        )
