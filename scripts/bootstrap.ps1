$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

# Load config
$Config = @{}
Get-Content "$Root\config.env" | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -notmatch "=") { return }
    $k, $v = $line -split "=", 2
    $Config[$k.Trim()] = $v.Trim()
}

Write-Host "=== step 1: build libopus and apply patches ==="
& "$Root\scripts\01_build_opus.ps1"

Write-Host "=== step 2: build tools ==="
& make tools

Write-Host "=== step 3: verify clip exists ==="
$clipPath = "$Root\data\pcm\$($Config.CLIP).raw"
if (-not (Test-Path $clipPath)) {
    Write-Error "missing $clipPath"
}

Write-Host "=== step 4: reference encode ==="
$env:PVQ_LOG = "$Root\logs\pvq_$($Config.CLIP)_$($Config.BITRATE)_$($Config.FRAME_MS)ms_$($Config.MODE).log"
& "$Root\build\encode_raw.exe" `
    $clipPath `
    "$Root\data\bitstreams\encoded\$($Config.CLIP)_base.opusraw" `
    --bitrate $Config.BITRATE --frame-ms $Config.FRAME_MS --mode $Config.MODE

Write-Host "=== step 5: reference decode ==="
& "$Root\build\decode_raw.exe" `
    "$Root\data\bitstreams\encoded\$($Config.CLIP)_base.opusraw" `
    "$Root\data\output\$($Config.CLIP)_base.raw"

Write-Host "=== step 6: verify ==="
& python "$Root\scripts\verify.py"
