import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
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
