[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [string]$RepoRoot,

    [string]$OutputFile,

    [switch]$PrintPrompt,

    [switch]$Yolo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-StoryboardRepoRoot {
    param([string]$ExplicitRoot)

    if ($ExplicitRoot) {
        return (Resolve-Path -LiteralPath $ExplicitRoot).ProviderPath
    }

    if ($PSScriptRoot) {
        return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
    }

    return (Get-Location).Path
}

function Get-HermesCommand {
    $candidates = @(
        (Get-Command hermes -ErrorAction SilentlyContinue),
        (Get-Command hermes.cmd -ErrorAction SilentlyContinue),
        (Get-Command hermes.exe -ErrorAction SilentlyContinue)
    ) | Where-Object { $null -ne $_ }

    if ($candidates.Count -gt 0) {
        return $candidates[0].Source
    }

    $fallbacks = @(
        'C:\Users\jston\.hermes\hermes-agent\venv\Scripts\hermes.exe',
        'C:\Users\jston\AppData\Roaming\npm\hermes.cmd'
    )

    foreach ($candidate in $fallbacks) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw 'Hermes CLI not found on PATH and known fallback locations were missing.'
}

$resolvedRepoRoot = Get-StoryboardRepoRoot -ExplicitRoot $RepoRoot
$hermesCommand = Get-HermesCommand

if ($PrintPrompt) {
    $Prompt
    return
}

Push-Location $resolvedRepoRoot
try {
    $arguments = @()
    if ($Yolo) {
        $arguments += '--yolo'
    }
    $arguments += '-z'
    $arguments += $Prompt

    $output = & $hermesCommand @arguments 2>&1
    $exitCode = $LASTEXITCODE

    if ($OutputFile) {
        $outputDir = Split-Path -Parent $OutputFile
        if ($outputDir) {
            New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        }
        $output | Out-File -FilePath $OutputFile -Encoding utf8
    }

    $output

    if ($exitCode -ne 0) {
        throw "Hermes command failed with exit code $exitCode."
    }
}
finally {
    Pop-Location
}
