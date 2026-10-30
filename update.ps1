param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+$')]
    [string]$Version
)
$ErrorActionPreference = 'Stop'

$telegramRoot = Join-Path $env:LOCALAPPDATA 'Codex/TelegramLocal'
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$telegramCurrentPlugin = Join-Path $codexHome 'plugins/telegram-local'
$telegramRuntimePython = Join-Path $telegramRoot 'runtime/Scripts/python.exe'
$archiveName = "codex-telegram-mcp-$Version.zip"
$checksumName = "$archiveName.sha256"

if (-not (Test-Path -LiteralPath (Join-Path $telegramCurrentPlugin '.codex-plugin/plugin.json'))) {
    throw 'Telegram Local is not installed for this Windows user. Run install.ps1 first.'
}

$release = Invoke-RestMethod -Headers @{ 'User-Agent' = 'Telegram-Local-Updater' } `
    -Uri "https://api.github.com/repos/akimsullec/codex-telegram-mcp/releases/tags/$Version"
$archiveAsset = $release.assets | Where-Object name -eq $archiveName | Select-Object -First 1
$checksumAsset = $release.assets | Where-Object name -eq $checksumName | Select-Object -First 1
if (-not $archiveAsset -or -not $checksumAsset) {
    throw "Release $Version does not contain both the ZIP archive and its SHA-256 checksum. No update was installed."
}

$temporaryRoot = Join-Path $env:TEMP ("telegram-local-update-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $archivePath = Join-Path $temporaryRoot $archiveName
    $checksumPath = Join-Path $temporaryRoot $checksumName
    Invoke-WebRequest -UseBasicParsing -Uri $archiveAsset.browser_download_url -OutFile $archivePath
    Invoke-WebRequest -UseBasicParsing -Uri $checksumAsset.browser_download_url -OutFile $checksumPath

    $checksumText = Get-Content -LiteralPath $checksumPath -Raw
    $checksumMatch = [regex]::Match($checksumText, '^([0-9a-fA-F]{64})\s+\*?' + [regex]::Escape($archiveName) + '\s*$')
    if (-not $checksumMatch.Success) { throw 'The release checksum file has an unexpected format. No update was installed.' }
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
    if ($actualHash -ne $checksumMatch.Groups[1].Value) { throw 'Release archive checksum mismatch. No update was installed.' }

    $extracted = Join-Path $temporaryRoot 'extracted'
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extracted
    $releaseRoot = Get-ChildItem -LiteralPath $extracted -Directory | Select-Object -First 1
    $releasePlugin = Join-Path $releaseRoot.FullName 'plugins/telegram-local'
    if (-not (Test-Path -LiteralPath (Join-Path $releasePlugin '.codex-plugin/plugin.json'))) {
        throw 'The verified release archive does not contain the Telegram Local plugin.'
    }

    $pluginVersion = (Get-Content -LiteralPath (Join-Path $releasePlugin '.codex-plugin/plugin.json') -Raw | ConvertFrom-Json).version
    if ("v$pluginVersion" -ne $Version) { throw 'Release tag and plugin version do not match.' }
    $currentVersion = (Get-Content -LiteralPath (Join-Path $telegramCurrentPlugin '.codex-plugin/plugin.json') -Raw | ConvertFrom-Json).version
    if ($currentVersion -eq $pluginVersion) { throw "Version $Version is already installed." }
    $backupPlugin = Join-Path $codexHome "plugins/telegram-local-backup-$currentVersion"
    if (Test-Path -LiteralPath $backupPlugin) { throw "A backup for $currentVersion already exists; no files were replaced." }

    $stagedPlugin = Join-Path $codexHome "plugins/telegram-local-staging-$pluginVersion"
    if (Test-Path -LiteralPath $stagedPlugin) { throw 'A staging directory already exists; inspect it before retrying.' }
    Copy-Item -LiteralPath $releasePlugin -Destination $stagedPlugin -Recurse
    if (-not (Test-Path -LiteralPath $telegramRuntimePython)) { throw 'The local Python runtime is missing. Re-run install.ps1.' }
    & $telegramRuntimePython -m pip install -r (Join-Path $stagedPlugin 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not update the plugin Python dependencies.' }

    Move-Item -LiteralPath $telegramCurrentPlugin -Destination $backupPlugin
    try {
        Move-Item -LiteralPath $stagedPlugin -Destination $telegramCurrentPlugin
    } catch {
        Move-Item -LiteralPath $backupPlugin -Destination $telegramCurrentPlugin
        throw
    }
    Write-Output "Verified release $Version installed. Previous files are in $backupPlugin. Start a new Codex chat to load it."
}
finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($temporaryRoot)
    $tempBase = [System.IO.Path]::GetFullPath($env:TEMP) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolvedTemp.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
