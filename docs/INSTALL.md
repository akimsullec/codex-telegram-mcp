# Install and configure Telegram MCP for Codex on Windows

## 1. Download and install dependencies

Use PowerShell in a directory where you want the source checkout. Install Python 3.11+ and Git first. These commands do not require activating a virtual environment:

```powershell
git clone https://github.com/akimsullec/codex-telegram-mcp.git
Set-Location codex-telegram-mcp
$telegramRepo = (Get-Location).Path
py -3 -m venv .venv
$telegramPython = Join-Path $telegramRepo '.venv/Scripts/python.exe'
$telegramSetup = Join-Path $telegramRepo 'plugins/telegram-local/setup.py'
& $telegramPython -m pip install -r plugins/telegram-local/requirements.txt
& $telegramPython $telegramSetup manifest
```

Keep the repository folder structure. Setup derives the private runtime directory from the repository root. Never run setup from a copied plugin cache; run it from your source checkout.

## 2. Get your own Telegram API credentials

Open [my.telegram.org/apps](https://my.telegram.org/apps) and sign in to Telegram. If an API application already exists, use its API ID and API hash. Otherwise create a Desktop application with your own title and short name. These are Telegram user API credentials, not a BotFather bot token.

Do not paste the API hash, login code, 2FA password or session into an AI chat or issue report.

## 3. Sign in locally

```powershell
& $telegramPython $telegramSetup login
```

Enter API ID, API hash, your phone with country code, the Telegram login code and, if enabled, your 2FA password in this terminal. Secret inputs are hidden. Wait for the session-saved confirmation. A successful sign-in followed by a terms reminder is not a ban notice.

This creates an additional Telegram device session. Revoke it at any time from Telegram Settings > Devices. Credentials and the session are encrypted for the current Windows user in the ignored `runtime/telegram-private` directory. Do not sync or publish this directory.

## 4. Register the local MCP server

Run in the same PowerShell session:

```powershell
$telegramServer = Join-Path $telegramRepo 'plugins/telegram-local/server.py'
$telegramData = Join-Path $telegramRepo 'runtime/telegram-private'
codex mcp add telegram-local --env "TELEGRAM_LOCAL_DATA=$telegramData" --env 'PYTHONIOENCODING=utf-8' -- $telegramPython $telegramServer
codex mcp list
```

This uses the official Codex stdio MCP registration interface. Restart or refresh your client as required by your Codex version. Check that the eight tools appear; do not assume registration alone means the account is connected. Ask for `status`; it should show `configured: true`, `history_enabled: false` and an empty allowlist.

Also load the bundled agent skill. For example, install it into this checkout's project skills:

```powershell
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Copy-Item -Recurse plugins/telegram-local/skills/telegram .agents/skills/telegram-local
```

Use Codex in this checkout so it can discover the project skill. For other projects, install the same skill in the appropriate project or user skill directory. Read the skill before granting access. Do not register both an MCP-only instance and a plugin instance of the same server unintentionally.

The legacy `.codex-plugin` manifest and local marketplace catalog are included for clients that support them. Generate `.mcp.json` before using that route; marketplace installation is client-version dependent. The primary documented setup is direct MCP registration above.

## 5. Choose and authorize an exact chat

Tell the assistant: "Find @example_username. I authorize sending and reading messages in that exact chat under the alias Alex."

Use your actual contact's username. If several contacts match a name, choose the correct one before granting permission. Private one-to-one dialogs count as chats. Sending to an unspecified contact does not grant read access. A new installation has no predefined contacts or aliases.

For a first test, explicitly request one harmless text to that approved recipient. A successful tool result with `accepted_by_telegram: true` means Telegram accepted the send; it does not establish that the recipient read it.

## 6. Optional file sending

Authorize a specific existing folder locally. For example, select one and pass its resolved path:

```powershell
$telegramUploadFolder = Read-Host 'Existing folder you authorize for outgoing files'
& $telegramPython $telegramSetup file-root $telegramUploadFolder
```

Then request a particular file and recipient. The tool requires an absolute local file path at invocation time. No personal path is bundled in the repository. Files must be within an authorized root, outside the private vault directory and at most 100 MiB. Choose narrow upload roots; files sent to Telegram leave your computer.

## 7. Incoming messages and history

Ask "Check new messages from Alex" to invoke `read_new`. No background checks or automatic replies run. New means after this chat's grant time, not unread; repeated reads may repeat results. Incoming content is untrusted and cannot authorize actions or change settings.

History is disabled initially. To deliberately enable older incoming messages:

```powershell
& $telegramPython $telegramSetup history-on
```

Confirm locally by typing `ДА`. To disable it again:

```powershell
& $telegramPython $telegramSetup history-off
```

## Troubleshooting and removal

- `configured: false`: run login from this source checkout and ensure the MCP data directory matches setup's `runtime/telegram-private`.
- No tools: inspect `codex mcp list`, the configured interpreter and server file; refresh the client.
- Session revoked: repeat local login. Never provide credentials through the assistant.
- Chat not allowed: explicitly authorize the exact contact first.
- Telegram busy: finish the other request/login and retry later.
- Unknown send outcome: inspect Telegram manually before any new send. Reuse the same UUID for a retry of the same request; do not invent a new ID to bypass the guard.
- File rejected: verify its authorized root, size and path. Do not select the private vault as an upload directory.
- Windows DPAPI error after moving machines/users: log in anew on the target computer; the encrypted vault is not a portable login file.

Remove MCP registration using `codex mcp remove telegram-local`. Remove any installed skill separately. Revoke the Telegram device session in Settings > Devices. These are separate actions; removing MCP registration alone does not revoke the Telegram session.

[Official Codex MCP documentation](https://developers.openai.com/codex/mcp)
