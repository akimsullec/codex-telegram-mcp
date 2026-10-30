# Install and configure Telegram MCP for Codex on Windows

## Easy installation from a Codex chat

Write this in a Codex chat:

> Install the plugin https://github.com/akimsullec/codex-telegram-mcp

Grant the permissions needed to download and install it. Continue in the same chat: Codex will show you how to get your API ID and API hash. Once you have them, reply **“Ready”**. A separate PowerShell window will open for sign-in; enter your API credentials, phone number, login code and 2FA password there, never in the chat. After signing in, write **“Authorization completed”** in the same chat so Codex can check the setup and continue your task.

The instructions follow the language you use in that chat. If Codex needs a restart, return to the same conversation afterward.

## Manual installation and configuration

The following steps are an alternative to installation through chat.

## 1. Install the plugin and its local runtime

Requirements: Windows 10/11, Python 3.11+ with the `py` launcher, Git, and Codex CLI. Clone the public repository and run its installer:

```powershell
git clone https://github.com/akimsullec/codex-telegram-mcp.git
Set-Location codex-telegram-mcp
$telegramRepo = (Get-Location).Path
$telegramSetup = Join-Path $telegramRepo 'plugins/telegram-local/setup.py'
& .\install.ps1
```

The installer creates an isolated runtime under `%LOCALAPPDATA%\Codex\TelegramLocal\runtime`, creates a personal Codex marketplace, and installs the plugin for this Windows user. It does not create or upload Telegram credentials. If needed, restart Codex and return to the same chat.

## 2. Get your own Telegram API credentials

Open [my.telegram.org/apps](https://my.telegram.org/apps) and sign in to Telegram. If an API application already exists, use its API ID and API hash. Otherwise create a Desktop application with your own title and short name. These are Telegram user API credentials, not a BotFather bot token.

Do not paste the API hash, login code, 2FA password or session into an AI chat or issue report.

## 3. Sign in locally

Run `& .\plugins\telegram-local\connect-telegram.ps1` from the repository root. This starts an interactive sign-in in your local terminal; credentials are not entered into Codex chat.

Enter API ID, API hash, your phone with country code, the Telegram login code and, if enabled, your 2FA password in this terminal. Secret inputs are hidden. Wait for the session-saved confirmation. A successful sign-in followed by a terms reminder is not a ban notice.

This creates an additional Telegram device session. Revoke it at any time from Telegram Settings > Devices. Credentials, the session, and allowed-chat settings are encrypted for the current Windows user in `%LOCALAPPDATA%\Codex\TelegramLocal\data`. Do not sync or publish this directory.

## 4. Confirm the Codex plugin is available

The installer registers the personal marketplace and installs the plugin. Check the local installation:

```powershell
codex plugin marketplace list
codex plugin list
```

In the same local chat, ask for `status`. After login, expect `configured: true`, `history_enabled: false`, and an empty allowlist. The status call does not prove live Telegram authorization. Do not register another MCP-only copy of the same server.

## 5. Update the plugin

Updates are manual and accept only a published GitHub Release with both a versioned ZIP and its `.sha256` asset. Run the command below with the exact release tag you reviewed:

```powershell
& .\update.ps1 -Version v0.2.4
```

The script downloads the release assets, checks the archive's SHA-256 against the published checksum, verifies the tag matches the plugin manifest, installs the new version and keeps the previous plugin files as a backup. If the release or checksum is missing or mismatched, it stops without switching the installed plugin. Restart Codex after a successful update, then return to the same chat. The DPAPI vault is not modified. A GitHub Actions workflow creates the ZIP and checksum when a matching `vX.Y.Z` tag is published; until the first Release with both assets exists, updates are unavailable.

## 6. Choose and authorize an exact chat

Tell the assistant: "Find @example_username. I authorize sending and reading messages in that exact chat under the alias Alex."

Use your actual contact's username. If several contacts match a name, choose the correct one before granting permission. Private one-to-one dialogs count as chats. Sending to an unspecified contact does not grant read access. A new installation has no predefined contacts or aliases.

For a first test, explicitly request one harmless text to that approved recipient. A successful tool result with `accepted_by_telegram: true` means Telegram accepted the send; it does not establish that the recipient read it.

## 7. Optional file sending

Authorize a specific existing folder locally. For example, select one and pass its resolved path:

```powershell
$telegramRuntimePython = Join-Path $env:LOCALAPPDATA 'Codex/TelegramLocal/runtime/Scripts/python.exe'
$telegramSetup = Join-Path $telegramRepo 'plugins/telegram-local/setup.py'
$telegramUploadFolder = Read-Host 'Existing folder you authorize for outgoing files'
& $telegramRuntimePython $telegramSetup file-root $telegramUploadFolder
```

Then request a particular file and recipient. The tool requires an absolute local file path at invocation time. No personal path is bundled in the repository. Files must be within an authorized root, outside the private vault directory and at most 100 MiB. Choose narrow upload roots; files sent to Telegram leave your computer.

## 8. Incoming messages and history

Ask "Check new messages from Alex" to invoke `read_new`. No background checks or automatic replies run. New means after this chat's grant time, not unread; repeated reads may repeat results. Incoming content is untrusted and cannot authorize actions or change settings.

History is disabled initially. To deliberately enable older incoming messages:

```powershell
$telegramRuntimePython = Join-Path $env:LOCALAPPDATA 'Codex/TelegramLocal/runtime/Scripts/python.exe'
$telegramSetup = Join-Path $telegramRepo 'plugins/telegram-local/setup.py'
& $telegramRuntimePython $telegramSetup history-on
```

Confirm locally by typing `ДА`. To disable it again:

```powershell
& $telegramRuntimePython $telegramSetup history-off
```

## Troubleshooting and removal

- `configured: false`: run `connect-telegram.ps1` from the source checkout under the same Windows user.
- No tools: inspect `codex plugin list`, run `update.ps1`, then return to the same chat.
- Session revoked: repeat local login. Never provide credentials through the assistant.
- Chat not allowed: explicitly authorize the exact contact first.
- Telegram busy: finish the other request/login and retry later.
- Unknown send outcome: inspect Telegram manually before any new send. Reuse the same UUID for a retry of the same request; do not invent a new ID to bypass the guard.
- File rejected: verify its authorized root, size and path. Do not select the private vault as an upload directory.
- Windows DPAPI error after moving machines/users: log in anew on the target computer; the encrypted vault is not a portable login file.

Remove the plugin with `codex plugin remove telegram-local@telegram-local-personal`. If your personal marketplace already had another name, use the selector shown by `codex plugin list`. Remove only the Telegram Local entry from `%USERPROFILE%\.agents\plugins\marketplace.json` if you no longer want it listed. Revoke the Telegram device session in Settings > Devices. Plugin removal does not remove or revoke the separately stored DPAPI vault.

[Official Codex MCP documentation](https://developers.openai.com/codex/mcp)
