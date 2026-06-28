[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VideoSlug,

    [string]$StoryboardPath,

    [string]$AssetBoardPath,

    [string]$OutputFile,

    [switch]$PrintPrompt,

    [switch]$StdoutOnly,

    [switch]$Yolo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$bridgeScript = Join-Path $PSScriptRoot 'hermes-bridge.ps1'

if (-not $StoryboardPath) {
    $StoryboardPath = "videos/$VideoSlug/storyboard.md"
}
if (-not $AssetBoardPath) {
    $AssetBoardPath = "videos/$VideoSlug/asset-board.csv"
}

$resolvedStoryboardPath = Join-Path $repoRoot $StoryboardPath
$resolvedAssetBoardPath = Join-Path $repoRoot $AssetBoardPath

if (-not (Test-Path -LiteralPath $resolvedStoryboardPath)) {
    throw "Storyboard not found: $resolvedStoryboardPath"
}
if (-not (Test-Path -LiteralPath $resolvedAssetBoardPath)) {
    throw "Asset board not found: $resolvedAssetBoardPath"
}

$outputInstruction = if ($StdoutOnly) {
@"
Return the recommendation in chat.
Include:
- recommended template lane
- 2-3 candidate Open Design templates or skills
- why each fits
- current asset risks
- the single best sample scene to generate first
"@
} else {
@"
Create or update only this file:
- videos/$VideoSlug/template-review.md

The file should include:
- recommended template lane
- 2-3 candidate Open Design templates or skills
- why each fits
- current asset risks
- the single best sample scene to generate first
"@
}

$prompt = @"
You are the Open Design Template Agent for storyboard-video-studio.

Repository root:
C:\Workspace\Repos\storyboard-video-studio

Follow:
- docs/template-discovery-plan.md
- docs/open-design-integration.md
- docs/agent-workflow.md

Inputs:
- $StoryboardPath
- $AssetBoardPath

Task:
Recommend the best Open Design template lane for video slug '$VideoSlug'.
Use Open Design as a template/style discovery surface only. Do not generate the final video.

$outputInstruction
"@

& $bridgeScript -Prompt $prompt -RepoRoot $repoRoot -OutputFile $OutputFile -PrintPrompt:$PrintPrompt -Yolo:$Yolo
