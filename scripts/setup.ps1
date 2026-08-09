$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$toolVersion = '2.1.1'
$toolRoot = Join-Path $projectRoot ".tools\tweego-$toolVersion"
$downloadRoot = Join-Path $projectRoot '.tools\downloads'
$archivePath = Join-Path $downloadRoot "tweego-$toolVersion-windows-x64.zip"
$tweegoPath = Join-Path $toolRoot 'tweego.exe'
$downloadUrl = "https://github.com/tmedwards/tweego/releases/download/v$toolVersion/tweego-$toolVersion-windows-x64.zip"
$expectedSha256 = '38102CC40906AE90B43F5ED1D97985D7C395376F54A14438E3FDA63C1C8FD28B'

if (Test-Path -LiteralPath $tweegoPath) {
    Write-Host "Tweego $toolVersion is already installed."
    & $tweegoPath --version
    exit $LASTEXITCODE
}

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

if (-not (Test-Path -LiteralPath $archivePath)) {
    Write-Host "Downloading Tweego $toolVersion..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing
}

$actualSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
if ($actualSha256 -ne $expectedSha256) {
    throw "Tweego checksum mismatch. Expected $expectedSha256, got $actualSha256."
}

if (Test-Path -LiteralPath $toolRoot) {
    throw "Tool directory exists but tweego.exe is missing: $toolRoot"
}

Write-Host 'Checksum verified. Extracting Tweego...'
New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
Expand-Archive -LiteralPath $archivePath -DestinationPath $toolRoot

if (-not (Test-Path -LiteralPath $tweegoPath)) {
    throw "tweego.exe was not found after extraction: $tweegoPath"
}

Write-Host "Tweego $toolVersion setup complete."
& $tweegoPath --version
exit $LASTEXITCODE
