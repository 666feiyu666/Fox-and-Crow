$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $projectRoot 'src\story.twee'
$outputPath = Join-Path $projectRoot 'dist\index.html'

& (Join-Path $PSScriptRoot 'build.ps1')
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE."
}

$source = Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8
$requiredSourceFragments = @(
    ':: StoryTitle',
    '"format": "SugarCube"',
    '<<set $loopCount = 0>>',
    '<<set $loopCount += 1>>',
    '<<goto '
)

foreach ($fragment in $requiredSourceFragments) {
    if (-not $source.Contains($fragment)) {
        throw "Story source is missing a required stage-one fragment: $fragment"
    }
}

$fixedChoiceCount = [regex]::Matches($source, '->').Count
if ($fixedChoiceCount -ne 5) {
    throw "Expected five fixed story choices, found $fixedChoiceCount."
}

if (-not (Test-Path -LiteralPath $outputPath)) {
    throw "Compiled HTML was not generated: $outputPath"
}

$output = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8
$requiredOutputFragments = @(
    '7A4F23F7-9B8B-4E75-9E84-3A626B435833',
    'SugarCube',
    '$loopCount += 1',
    'The same day, once more'
)

foreach ($fragment in $requiredOutputFragments) {
    if (-not $output.Contains($fragment)) {
        throw "Compiled HTML is missing an expected fragment: $fragment"
    }
}

if ((Get-Item -LiteralPath $outputPath).Length -lt 100000) {
    throw 'Compiled HTML is unexpectedly small; the story format may not be embedded.'
}

Write-Host 'Verification passed: fixed path, loop state, and standalone HTML are ready.'
