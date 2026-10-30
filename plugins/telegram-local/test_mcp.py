import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class StartupImportTests(unittest.TestCase):
    def test_server_import_does_not_load_telegram_runtime(self):
        server_dir = Path(__file__).resolve().parent
        script = (
            "import sys; import server; "
            "assert 'telethon' not in sys.modules; "
            "assert 'core' not in sys.modules; "
            "assert 'transport' not in sys.modules"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_configured_manifest_uses_isolated_runtime_directly(self):
        plugin_dir = Path(__file__).resolve().parent
        setup_path = plugin_dir / "setup.py"
        spec = importlib.util.spec_from_file_location(
            "telegram_local_setup", setup_path
        )
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "installed-plugin"
            runtime_python = root / "runtime" / "Scripts" / "python.exe"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                "{}", encoding="utf-8"
            )
            runtime_python.parent.mkdir(parents=True)
            runtime_python.write_bytes(b"")

            with patch.dict(
                os.environ,
                {"TELEGRAM_LOCAL_RUNTIME": str(runtime_python.parents[1])},
            ):
                setup.configure_manifest(plugin)

            manifest = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))
            server = manifest["mcpServers"]["telegram-local"]
            self.assertEqual(server["command"], str(runtime_python))
            self.assertEqual(server["args"], [str(plugin.resolve() / "server.py")])
            self.assertEqual(server["env"], {"PYTHONIOENCODING": "utf-8"})


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_manifest_starts_from_unrelated_directory(self):
        import setup

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugin with spaces"
            shutil.copytree(Path(__file__).parent, plugin,
                            ignore=shutil.ignore_patterns("__pycache__"))
            with patch.object(setup, "runtime_dir", return_value=Path(sys.executable).parents[1]):
                setup.configure_manifest(plugin)
            server = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["telegram-local"]
            parameters = StdioServerParameters(
                command=server["command"], args=server["args"], cwd=str(root),
                env=dict(os.environ, **server["env"], TELEGRAM_LOCAL_DATA=str(root / "data")),
            )
            async with (
                asyncio.timeout(20),
                stdio_client(parameters) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                self.assertIn("send_text", {tool.name for tool in (await session.list_tools()).tools})

    async def test_stdio_handshake_tools_and_offline_status(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(
                os.environ, TELEGRAM_LOCAL_DATA=directory, PYTHONIOENCODING="utf-8"
            )
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).with_name("server.py"))],
                env=environment,
            )
            async with (
                asyncio.timeout(20),
                stdio_client(parameters) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                self.assertEqual(
                    names,
                    {
                        "status",
                        "find_chats",
                        "allow_chat",
                        "revoke_chat",
                        "send_text",
                        "send_file",
                        "read_new",
                        "read_history",
                    },
                )
                result = await session.call_tool("status", {})
                self.assertFalse(result.isError)
                import json

                content = json.loads(result.content[0].text)
                self.assertFalse(content["configured"])
                self.assertFalse(content["history_enabled"])
                self.assertEqual(content["allowed_chats"], [])
