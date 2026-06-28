[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VideoSlug,

    [string]$StoryboardPath,

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

$resolvedStoryboardPath = Join-Path $repoRoot $StoryboardPath
if (-not (Test-Path -LiteralPath $resolvedStoryboardPath)) {
    throw "Storyboard not found: $resolvedStoryboardPath"
}

$outputInstruction = if ($StdoutOnly) {
@"
Return the planning pass in chat instead of writing files.
Structure the response in this order:
1. asset-board.csv as a fenced csv block
2. source-notes.md as a fenced markdown block
3. credits.md as a fenced markdown block
4. Asset Research Handoff summary
"@
} else {
@"
Create or update only these files under videos/$VideoSlug/:
- asset-board.csv
- sources/source-notes.md
- sources/credits.md
Do not download files yet.
End with the Asset Research Handoff summary.
"@
}

$prompt = @"
You are the Asset Researcher Agent for storyboard-video-studio.

Repository root:
C:\Workspace\Repos\storyboard-video-studio

Follow:
- docs/asset-researcher-agent.md
- docs/asset-researcher-runbook.md
- templates/assets/asset-board-template.csv

Input:
- $StoryboardPath

Task:
Run the Planning-Only Asset Research Pass for video slug '$VideoSlug'.

Rules:
- Do not download files yet.
- Do not render video.
- Do not rewrite the storyboard or script.
- For each scene, propose 2-4 asset candidates or source strategies.
- Prefer stable/public sources.
- If licensing is unclear, mark needs-review or high risk.

$outputInstruction
"@

& $bridgeScript -Prompt $prompt -RepoRoot $repoRoot -OutputFile $OutputFile -PrintPrompt:$PrintPrompt -Yolo:$Yolo
