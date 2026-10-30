import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import server
import setup
from onboarding import AUTH_INSTRUCTIONS
from transport import make_client


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_rejects_captured_terminal_before_prompting(self):
        with (patch.object(sys.stdin, "isatty", return_value=False),
              patch("getpass.getpass") as prompt,
              self.assertRaises(RuntimeError)):
            await setup.login(MagicMock())
        prompt.assert_not_called()

    def test_missing_credentials_return_shared_instruction(self):
        with self.assertRaises(RuntimeError) as error:
            make_client({})
        self.assertEqual(str(error.exception), AUTH_INSTRUCTIONS)

    async def test_status_returns_shared_instruction_without_network(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(server, "PRIVATE", Path(directory)),
        ):
            result = await server.status()
        self.assertEqual(result["onboarding_instructions"], AUTH_INSTRUCTIONS)
        self.assertEqual(result["next_step"], "await_user_confirmation")

    async def test_missing_session_stops_before_network(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(server, "PRIVATE", Path(directory)),
            patch("transport.make_client") as client,
            self.assertRaises(RuntimeError) as error,
        ):
            await server.find_chats("test")
        client.assert_not_called()
        self.assertEqual(str(error.exception), AUTH_INSTRUCTIONS)

    def test_installer_cli_returns_exact_same_instruction(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("setup.py")), "onboarding"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=__import__("os").environ | {"PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.stdout.strip(), AUTH_INSTRUCTIONS)

    async def test_revoked_session_returns_same_instruction(self):
        client = MagicMock()
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.is_user_authorized = AsyncMock(return_value=False)
        client.session.save.return_value = "synthetic-session"
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(server, "PRIVATE", Path(directory)),
            patch.object(server, "auth_configured", return_value=True),
            patch("transport.make_client", return_value=client),
            self.assertRaises(RuntimeError) as error,
        ):
            await server.find_chats("test")
        self.assertEqual(str(error.exception), AUTH_INSTRUCTIONS)
        client.disconnect.assert_awaited_once()
