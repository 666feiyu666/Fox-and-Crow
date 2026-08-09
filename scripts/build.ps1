$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$tweegoPath = Join-Path $projectRoot '.tools\tweego-2.1.1\tweego.exe'
$sourcePath = Join-Path $projectRoot 'src'
$distPath = Join-Path $projectRoot 'dist'
$outputPath = Join-Path $distPath 'index.html'

if (-not (Test-Path -LiteralPath $tweegoPath)) {
    Write-Host 'Tweego is missing. Running environment setup...'
    & (Join-Path $PSScriptRoot 'setup.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "Environment setup failed with exit code $LASTEXITCODE."
    }
}

New-Item -ItemType Directory -Force -Path $distPath | Out-Null

Write-Host 'Building the Twine story...'
& $tweegoPath -f sugarcube-2 -o $outputPath $sourcePath
if ($LASTEXITCODE -ne 0) {
    throw "Tweego build failed with exit code $LASTEXITCODE."
}

Write-Host "Build complete: $outputPath"
