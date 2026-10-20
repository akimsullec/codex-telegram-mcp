$ErrorActionPreference = 'Stop'
$telegramLaunchConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot '.mcp.json') -Raw | ConvertFrom-Json
$telegramPython = $telegramLaunchConfig.mcpServers.'telegram-local'.command
& $telegramPython (Join-Path $PSScriptRoot 'setup.py') login
if ($LASTEXITCODE -ne 0) { throw 'Telegram login was not completed.' }
