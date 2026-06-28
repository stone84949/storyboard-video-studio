[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VideoSlug,

    [Parameter(Mandatory = $true)]
    [string]$Topic,

    [string]$Audience = 'general audience',

    [string]$Goal = 'Create a practical storyboard-ready video brief.',

    [string]$OutputFile,

    [switch]$PrintPrompt,

    [switch]$StdoutOnly,

    [switch]$Yolo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$bridgeScript = Join-Path $PSScriptRoot 'hermes-bridge.ps1'

$outputInstruction = if ($StdoutOnly) {
@"
Return the brief in chat instead of writing files.
Include these sections:
- working title
- audience
- goal
- angle
- 6-10 scene storyboard outline
- likely asset needs
- biggest research risks
- recommended next step
"@
} else {
@"
Create or update only these files under videos/$VideoSlug/:
- brief.md
- storyboard.md

brief.md should capture the angle, audience, asset risks, and research notes.
storyboard.md should contain a practical 6-10 scene storyboard outline ready for the Asset Researcher pass.
"@
}

$prompt = @"
You are the Producer / Storyboard Agent for storyboard-video-studio.

Repository root:
C:\Workspace\Repos\storyboard-video-studio

Follow:
- README.md
- docs/agent-workflow.md
- docs/open-design-integration.md

Video slug: $VideoSlug
Topic: $Topic
Audience: $Audience
Goal: $Goal

Task:
Create a concise producer brief and storyboard starter for the first pass.
Keep the angle practical and suited to a 2+ minute explainer workflow.
Do not render video. Do not do deep asset research yet.

$outputInstruction
"@

& $bridgeScript -Prompt $prompt -RepoRoot $repoRoot -OutputFile $OutputFile -PrintPrompt:$PrintPrompt -Yolo:$Yolo
