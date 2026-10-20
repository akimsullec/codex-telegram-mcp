import copy
import tempfile
import unittest
import uuid
from pathlib import Path

from core import TelegramService
from vault import initial_state


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.rows = []
        self.fail = False

    async def resolve(self, reference):
        return {"chat_id": int(reference), "title": "Test", "kind": "user", "peer": {}}

    async def send_text(self, chat, text, request_id):
        self.calls.append(("text", chat["chat_id"]))
        if self.fail:
            raise TimeoutError("test")
        return {"message_id": 12, "chat_id": chat["chat_id"]}

    async def send_file(self, chat, path, caption):
        self.calls.append(("file", chat["chat_id"]))
        return {"message_id": 13, "chat_id": chat["chat_id"]}

    async def read(self, chat, cutoff, limit, before_id):
        self.calls.append(("read", cutoff, limit, before_id))
        return self.rows


class PolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.state = initial_state()
        self.state["file_roots"] = [str(self.root)]
        self.saved = []
        self.transport = FakeTransport()
        self.service = TelegramService(
            self.state,
            lambda s: self.saved.append(copy.deepcopy(s)),
            self.transport,
            self.root / "private",
            clock=lambda: 100.1,
        )

    def tearDown(self):
        self.tmp.cleanup()

    async def permit(self, alias="Contact", chat_id="1"):
        await self.service.allow_chat(chat_id, alias)

    async def test_unselected_cannot_send_or_read(self):
        with self.assertRaises(PermissionError):
            await self.service.send("unknown", str(uuid.uuid4()), text="hi")
        with self.assertRaises(PermissionError):
            await self.service.read("unknown")
        self.assertEqual(self.transport.calls, [])

    async def test_exact_alias_and_no_silent_rebind(self):
        await self.permit()
        self.assertEqual(self.service.allowed(" CONTACT ")["chat_id"], 1)
        with self.assertRaises(ValueError):
            await self.service.allow_chat("2", "Contact")
        self.assertEqual(self.service.allowed("Contact")["chat_id"], 1)

    async def test_revoke_removes_every_alias(self):
        await self.permit()
        await self.permit("Second")
        self.service.revoke_chat("Contact")
        self.assertEqual(self.service.list_allowed(), [])

    async def test_history_is_off_before_transport(self):
        await self.permit()
        with self.assertRaises(PermissionError):
            await self.service.read("Contact", history=True)
        self.assertEqual(self.transport.calls, [])

    async def test_cutoff_and_outgoing_filter_and_pagination(self):
        await self.permit()
        self.transport.rows = [
            {"id": i, "date": date, "outgoing": out}
            for i, date, out in [
                (1, 99, False),
                (2, 101, True),
                (3, 101, False),
                (4, 102, False),
            ]
        ]
        result = await self.service.read("Contact", limit=1)
        self.assertEqual([m["id"] for m in result["messages"]], [4])
        self.assertEqual(result["next_before_id"], 4)
        self.assertEqual(self.transport.calls[-1][1], 101)

    async def test_send_deduplication_and_id_reuse_rejected(self):
        await self.permit()
        request = str(uuid.uuid4())
        await self.service.send("Contact", request, text="hi")
        result = await self.service.send("Contact", request, text="hi")
        self.assertTrue(result["deduplicated"])
        self.assertEqual(len(self.transport.calls), 1)
        with self.assertRaises(ValueError):
            await self.service.send("Contact", request, text="changed")

    async def test_unknown_send_result_never_automatically_retries(self):
        await self.permit()
        self.transport.fail = True
        request = str(uuid.uuid4())
        with self.assertRaises(TimeoutError):
            await self.service.send("Contact", request, text="hi")
        with self.assertRaises(RuntimeError):
            await self.service.send("Contact", request, text="hi")
        self.assertEqual(len(self.transport.calls), 1)

    async def test_private_file_denied_even_under_allowed_root(self):
        await self.permit()
        (self.root / "private").mkdir()
        secret = self.root / "private" / "session.dpapi"
        secret.write_bytes(b"synthetic")
        with self.assertRaises(PermissionError):
            await self.service.send("Contact", str(uuid.uuid4()), path=str(secret))
        self.assertEqual(self.transport.calls, [])

    async def test_normal_file_send(self):
        await self.permit()
        target = self.root / "test.txt"
        target.write_text("synthetic")
        await self.service.send("Contact", str(uuid.uuid4()), path=str(target))
        self.assertEqual(self.transport.calls, [("file", 1)])

    async def test_file_outside_allowed_root_denied(self):
        self.state["file_roots"] = []
        target = self.root / "test.txt"
        target.write_text("synthetic")
        with self.assertRaises(PermissionError):
            self.service.checked_file(str(target))

    async def test_history_can_be_enabled_explicitly(self):
        await self.permit()
        self.state["history_enabled"] = True
        await self.service.read("Contact", history=True)
        self.assertEqual(self.transport.calls[-1][1], 0)

    async def test_adapter_uses_no_background_updates(self):
        from transport import client_options

        self.assertFalse(client_options()["receive_updates"])
        self.assertFalse(client_options()["catch_up"])

    async def test_alias_regrant_does_not_reset_permission_time(self):
        await self.permit()
        self.service.clock = lambda: 999
        await self.permit()
        await self.permit("Second")
        self.assertEqual(self.service.allowed("Second")["allowed_at"], 101)

    async def test_invalid_alias_does_not_resolve(self):
        with self.assertRaises(ValueError):
            await self.permit("  ")

    async def test_invalid_message_arguments_do_not_send(self):
        await self.permit()
        for arguments in [
            {},
            {"text": "hi", "path": "x"},
            {"text": " "},
            {"text": "x" * 4097},
            {"text": "hi", "caption": "x" * 1025},
        ]:
            with self.assertRaises(ValueError):
                await self.service.send("Contact", str(uuid.uuid4()), **arguments)
        self.assertEqual(self.transport.calls, [])

    async def test_invalid_page_arguments_do_not_read(self):
        await self.permit()
        for arguments in [{"limit": 0}, {"limit": 101}, {"before_id": -1}]:
            with self.assertRaises(ValueError):
                await self.service.read("Contact", **arguments)
        self.assertEqual(self.transport.calls, [])

    async def test_relative_path_and_directory_denied(self):
        with self.assertRaises(ValueError):
            self.service.checked_file("relative.txt")
        with self.assertRaises(ValueError):
            self.service.checked_file(str(self.root))

    async def test_oversized_file_denied(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        target = self.root / "synthetic.bin"
        target.write_bytes(b"synthetic")
        # Mock is_file as the synthetic stat does not contain st_mode.
        with (
            patch.object(
                Path, "stat", return_value=SimpleNamespace(st_size=101 * 1024 * 1024)
            ),
            patch.object(Path, "is_file", return_value=True),
            self.assertRaises(ValueError),
        ):
            self.service.checked_file(str(target))


class VaultTests(unittest.TestCase):
    def test_dpapi_round_trip_and_no_plaintext_secret(self):
        from vault import Vault

        with tempfile.TemporaryDirectory() as directory:
            vault = Vault(directory)
            with vault.locked():
                self.assertEqual(vault.load(), initial_state())
                state = initial_state()
                state["session"] = "SYNTHETIC_SECRET_NEVER_A_REAL_SESSION"
                vault.save(state)
                self.assertNotIn(state["session"].encode(), vault.path.read_bytes())
                self.assertEqual(vault.load(), state)


if __name__ == "__main__":
    unittest.main()
