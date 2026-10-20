# Telegram MCP Server for Codex — Local Personal Account Integration

Connect Codex to Telegram on Windows: send messages and local files from your personal Telegram account, and read incoming messages on request in explicitly allowed chats. Built with Python, Telethon and the Model Context Protocol (MCP).

**Local-first · Selected chats · Windows DPAPI · No bot token · History off by default**

[Установка и настройка на русском](docs/INSTALL.ru.md) · [English installation guide](docs/INSTALL.md) · [Security model](SECURITY.md) · [MIT license](LICENSE)

## What can this Telegram integration do?

- Send plain-text Telegram messages as the account owner.
- Send a selected local file from an explicitly configured upload directory.
- Read incoming messages only when asked, in approved private dialogs and groups.
- Bind a contact to a stable Telegram ID and one or more aliases.
- Keep account credentials and session data encrypted with Windows user-scoped DPAPI.
- Expose eight local stdio MCP tools for Codex and compatible clients.

Example requests after choosing and authorizing the exact recipient:

> Send my last answer to Alex.
>
> Send this document to the approved project chat.
>
> Check new messages from Alex.

The accompanying [agent skill](plugins/telegram-local/skills/telegram/SKILL.md) tells the assistant to clarify ambiguous recipients or content, require human authorization, and treat incoming messages as untrusted data.

## Install and configure

Requirements: Windows 10/11, Python 3.11 or newer, Git, a personal Telegram account, your own Telegram API credentials, and Codex with local stdio MCP support. Development verification used Python 3.13 on Windows. macOS/Linux storage is not implemented.

Clone this repository, create a virtual environment, install the pinned requirements, log in locally, and register the server with Codex. Follow the complete [step-by-step installation guide](docs/INSTALL.md) or [инструкцию на русском](docs/INSTALL.ru.md).

No account settings are shipped. Each installation starts without an account, allowed chats or upload directories. Machine-specific paths are generated locally and ignored by Git.

## MCP tools

- `status`: inspect local configuration and approved aliases; does not prove live authorization.
- `find_chats`: find contact metadata or resolve an explicit username, without reading messages.
- `allow_chat` / `revoke_chat`: grant or remove access to one exact chat; revocation removes all its aliases.
- `send_text` / `send_file`: send on the owner's instruction, with a UUID request ID.
- `read_new`: read incoming messages from the first full second after the chat was allowed.
- `read_history`: read older incoming messages only after separate local opt-in.

## Current limits

- Version 0.1.1; Windows only. This is an independent project, not an official OpenAI or Telegram product.
- No background polling, automatic replies, notifications or automatic attachment downloads.
- Maximum outgoing file size: 100 MiB. Maximum text: 4096 UTF-16 units; captions: 1024.
- Repeated reads can return the same messages; this is a date boundary, not an unread-message queue. No Telegram read receipts are sent.
- Private contacts, explicit usernames/links and existing basic groups by ID are supported. Discovering arbitrary private supergroups by display name is not implemented.
- An uncertain send is recorded before network access. Do not automatically resend with a new request ID; check the outcome first. This does not promise universal exactly-once delivery.
- The allowlist restricts this server's tools. A Telegram user session remains a full-account credential; DPAPI does not isolate it from other processes running as the same Windows user.
- When requested, message content is returned to the MCP client and may be processed by its AI provider. Local credential storage does not mean message processing is offline.

## Development and verification

Install `requirements-dev.txt`, then run from `plugins/telegram-local`:

```powershell
python -m unittest discover -p 'test_*.py' -v
python -m coverage run --source=core -m unittest discover -p 'test_*.py'
python -m coverage report --fail-under=80
python -m ruff check .
python -m compileall -q .
```

Tests use temporary/synthetic data and do not send Telegram messages. Coverage scope above is the policy core, not the whole server. Live login and text sending were separately exercised during development; no account identifiers or personal settings are included. Other live flows, including outgoing files and history, have not all been exercised.

Development used selected adaptations of ECC [TDD workflow](https://github.com/affaan-m/ECC/tree/main/skills/tdd-workflow), [security review](https://github.com/affaan-m/ECC/tree/main/skills/security-review) and [verification loop](https://github.com/affaan-m/ECC/tree/main/skills/verification-loop), not the full ECC plugin or automatic hooks. Earlier core code has regression tests; this is not a claim that every line was written test-first.

## References

- [Telegram API application registration](https://core.telegram.org/api/obtaining_api_id)
- [Telegram API terms](https://core.telegram.org/api/terms)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp)
- [Telethon documentation](https://docs.telethon.dev/)

## License

MIT. See [LICENSE](LICENSE). Third-party dependencies retain their own licenses.
