$ErrorActionPreference = 'Stop'
$telegramPython = Join-Path $env:LOCALAPPDATA 'Codex/TelegramLocal/runtime/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $telegramPython)) {
    throw 'Run install.ps1 from the repository root before connecting Telegram.'
}
& $telegramPython (Join-Path $PSScriptRoot 'setup.py') login
if ($LASTEXITCODE -ne 0) { throw 'Telegram login was not completed.' }
