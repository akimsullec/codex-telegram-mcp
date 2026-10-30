$ErrorActionPreference = 'Stop'

$telegramRepo = $PSScriptRoot
$telegramSetup = Join-Path $telegramRepo 'plugins/telegram-local/setup.py'
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$telegramPlugin = Join-Path $codexHome 'plugins/telegram-local'
$telegramMarketplaceFile = Join-Path $env:USERPROFILE '.agents/plugins/marketplace.json'

$pythonCommands = @(Get-Command py -All -ErrorAction SilentlyContinue)
$pythonLauncher = $pythonCommands |
    Where-Object { $_.CommandType -eq 'Application' -and $_.Source -match '(?i)\\py\.exe$' -and $_.Source -notmatch '(?i)\\\.local\\bin\\' } |
    Select-Object -First 1
if (-not $pythonLauncher) { throw 'Windows py.exe was not found. Install Python 3.11+ and retry.' }

$codexCommands = @(Get-Command codex -All -ErrorAction SilentlyContinue)
$codexCli = $codexCommands |
    Where-Object { $_.CommandType -eq 'Application' -and $_.Source -match '(?i)\\codex\.exe$' -and $_.Source -notmatch '(?i)\\\.local\\bin\\' } |
    Select-Object -First 1
if (-not $codexCli) { throw 'Windows codex.exe was not found. Install Codex CLI and retry.' }

& $pythonLauncher.Source -3 $telegramSetup install-runtime
if ($LASTEXITCODE -ne 0) { throw 'Python runtime setup failed.' }

if (-not (Test-Path -LiteralPath (Join-Path $telegramPlugin '.codex-plugin/plugin.json'))) {
    if (Test-Path -LiteralPath $telegramPlugin) { throw 'A Telegram Local plugin directory already exists but has no recognized manifest.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $telegramPlugin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $telegramRepo 'plugins/telegram-local') -Destination $telegramPlugin -Recurse
}

& $pythonLauncher.Source -3 $telegramSetup configure-manifest $telegramPlugin
if ($LASTEXITCODE -ne 0) { throw 'Could not configure the installed plugin to use its isolated Python runtime.' }

$marketplaceDirectory = Split-Path -Parent $telegramMarketplaceFile
New-Item -ItemType Directory -Force -Path $marketplaceDirectory | Out-Null
$marketplaceRoot = [System.IO.Path]::GetFullPath($env:USERPROFILE)
$marketplaceUri = [System.Uri]($marketplaceRoot + [System.IO.Path]::DirectorySeparatorChar)
$pluginUri = [System.Uri]([System.IO.Path]::GetFullPath($telegramPlugin))
$sourcePath = './' + [System.Uri]::UnescapeDataString($marketplaceUri.MakeRelativeUri($pluginUri).ToString())
$entry = @{
    name = 'telegram-local'
    source = @{ source = 'local'; path = $sourcePath }
    policy = @{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
    category = 'Productivity'
}
$catalogName = 'telegram-local-personal'
if (Test-Path -LiteralPath $telegramMarketplaceFile) {
    $catalog = Get-Content -LiteralPath $telegramMarketplaceFile -Raw | ConvertFrom-Json
    if (-not $catalog.name -or -not $catalog.plugins) { throw 'The existing personal marketplace has an unexpected format; it was not modified.' }
    $catalogName = $catalog.name
    $existingEntry = @($catalog.plugins | Where-Object name -eq 'telegram-local') | Select-Object -First 1
    if ($existingEntry) {
        if ($existingEntry.source.path -ne $entry.source.path) {
            if ($catalog.name -eq 'telegram-local-personal' -and $existingEntry.source.path -eq './../../.codex/plugins/telegram-local') {
                $existingEntry.source.path = $entry.source.path
            } else {
                throw 'A different Telegram Local plugin entry already exists in your personal marketplace.'
            }
        }
    } else {
        $catalog.plugins = @($catalog.plugins) + @($entry)
    }
} else {
    $catalog = @{
        name = $catalogName
        interface = @{ displayName = 'Personal Codex plugins' }
        plugins = @($entry)
    }
}
$catalogJson = $catalog | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($telegramMarketplaceFile, $catalogJson, [System.Text.UTF8Encoding]::new($false))

$pluginSelector = "telegram-local@$catalogName"
$pluginStateText = & $codexCli.Source plugin list --marketplace $catalogName --json
if ($LASTEXITCODE -ne 0) { throw 'Could not read plugins from the personal marketplace.' }
$pluginState = $pluginStateText | ConvertFrom-Json
$installedPlugin = @($pluginState.installed | Where-Object pluginId -eq $pluginSelector) | Select-Object -First 1
if (-not $installedPlugin) {
    & $codexCli.Source plugin add $pluginSelector
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Telegram Local from the personal marketplace.' }
} elseif (-not $installedPlugin.enabled) {
    throw 'Telegram Local is installed but disabled. Enable it in the Codex plugin browser.'
}

Write-Output 'Plugin installed. Codex: show the following instructions in the SAME chat in the language the user is using in that chat. Preserve links, formatting and safety rules; translate the confirmation words too. For Russian preserve the approved text. Wait for explicit readiness confirmation. Do not start login yet. Follow the installed telegram skill and dialogue.md.'
& $pythonLauncher.Source -3 $telegramSetup onboarding
if ($LASTEXITCODE -ne 0) { throw 'Could not display Telegram authorization instructions.' }
