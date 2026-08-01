<#
.SYNOPSIS
    Builds a portable Windows release of MusicMaker.

.DESCRIPTION
    Run this script from Windows PowerShell in the project directory. It installs
    the Python dependencies, downloads a static FFmpeg build, creates a windowed
    one-file executable, and writes a distributable ZIP to release/.
#!>

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ was not found. Install Python from python.org and retry."
}

python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path vendor | Out-Null

if (-not (Test-Path vendor\ffmpeg.exe)) {
    $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    $archive = Join-Path $env:TEMP "musicmaker-ffmpeg.zip"
    $extract = Join-Path $env:TEMP "musicmaker-ffmpeg"
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $archive
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Expand-Archive -Path $archive -DestinationPath $extract -Force
    $binary = Get-ChildItem $extract -Filter ffmpeg.exe -Recurse | Select-Object -First 1
    if (-not $binary) { throw "ffmpeg.exe was not found in the downloaded archive." }
    Copy-Item $binary.FullName vendor\ffmpeg.exe -Force
    $license = Get-ChildItem $extract -Filter LICENSE.txt -Recurse | Select-Object -First 1
    if ($license) { Copy-Item $license.FullName vendor\FFMPEG-LICENSE.txt -Force }
}

& .\build.bat
if (-not (Test-Path dist\MusicMaker.exe)) { throw "The executable was not created." }

$releaseDirectory = Join-Path $projectRoot "release"
New-Item -ItemType Directory -Force -Path $releaseDirectory | Out-Null
Copy-Item dist\MusicMaker.exe $releaseDirectory\MusicMaker.exe -Force
Copy-Item README.md $releaseDirectory\README.txt -Force
if (Test-Path vendor\FFMPEG-LICENSE.txt) {
    Copy-Item vendor\FFMPEG-LICENSE.txt $releaseDirectory\FFMPEG-LICENSE.txt -Force
}
$zipPath = Join-Path $projectRoot "MusicMaker-Windows-x64.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$releaseDirectory\*" -DestinationPath $zipPath -Force
Write-Host "Portable release created: $zipPath"
