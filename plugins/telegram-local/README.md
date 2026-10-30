# Telegram Local MCP server

See the repository [README](../../README.md), [English setup guide](../../docs/INSTALL.md), [русскую инструкцию](../../docs/INSTALL.ru.md) and [security model](../../SECURITY.md).

The committed `.mcp.json` contains only a portable Windows launcher; it does not contain account settings or secrets. Run `install.ps1` from the repository root to provision the isolated runtime and install the personal Codex marketplace plugin. Per-user credentials and chat allowlist are stored outside the plugin under `%LOCALAPPDATA%\Codex\TelegramLocal\data`.
