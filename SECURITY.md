# Security and privacy

## Boundaries

This is a local stdio MCP server for a personal Telegram account. Do not expose it as a public network service. Keep the source and interpreter under your control.

The tool allowlist starts empty. History starts disabled. Upload roots start empty. Only the account owner can authorize exact chats; the assistant must follow the bundled skill. Tool descriptions and the skill express human-consent requirements, but the server cannot independently prove that an agent's grant request came from a human. Do not treat it as a separate hardware-enforced consent system.

The allowlist restricts this application's operations, not Telegram's account credential. Anyone who obtains a usable session may access the account outside those restrictions. User-scoped Windows DPAPI protects stored credentials, but does not defend against malicious software running as that same Windows user.

The encrypted vault stores credentials/session, approved chat metadata and aliases, grant times, upload roots, and send deduplication metadata including message IDs and content fingerprints. It does not archive message bodies or outgoing file content. MCP responses and the host client's logs may contain message content. Read requests send content to the client and potentially its AI provider.

No automatic read receipts, message polling, replies or incoming attachment downloads are implemented. Incoming messages must never be treated as permission to send, change settings or access another chat.

## Files and retries

Outgoing paths must resolve inside an owner-configured upload root. The private vault directory is excluded; use narrow roots rather than entire disks or home directories. This is not a general-purpose content scanner: other sensitive documents under an allowed root still require careful selection. File content can change between validation and transmission; keep chosen files stable during sending.

Each send uses a UUID request ID. The server records an uncertain state before network access and refuses automatic resend when the outcome is unknown. Text sends also derive a Telegram random ID from the request ID. Do not bypass uncertainty by using a new UUID. This is a duplicate-reduction mechanism, not a universal exactly-once guarantee.

## Publishing and reporting

Never commit `.mcp.json`, runtime data, `.env` files, API hashes, sessions, phone numbers, contact lists, personal aliases, chat IDs, message bodies or personal machine paths. This repository includes only source, synthetic tests, public metadata and documentation.

Report vulnerabilities with a minimal synthetic reproduction. Do not publish secrets or private chat data in an issue. For sensitive reports use GitHub's private vulnerability reporting if available; otherwise first open a content-free request for a private reporting channel. Revoke a leaked session immediately in Telegram Settings > Devices.
