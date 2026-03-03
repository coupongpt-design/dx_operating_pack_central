param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $projectRoot

Write-Host "[build] project root: $projectRoot"

foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) {
        Write-Host "[build] remove $dir"
        Remove-Item $dir -Recurse -Force
    }
}

$pyi = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyi) {
    Write-Host "[build] pyinstaller not found. installing..."
    python -m pip install --upgrade pyinstaller
}

Write-Host "[build] running PyInstaller"
python -m PyInstaller --noconfirm ImageMacro.spec

$distDir = Join-Path $projectRoot "dist\ImageMacro"
$exePath = Join-Path $distDir "ImageMacro.exe"
if (-not (Test-Path $exePath)) {
    throw "[build] exe not found: $exePath"
}

# Keep a plain markdown copy beside exe for easy manual access.
$guideSrc = Join-Path $projectRoot "USER_GUIDE.md"
if (Test-Path $guideSrc) {
    Copy-Item $guideSrc (Join-Path $distDir "USER_GUIDE.md") -Force
}

if (-not $SkipSmoke) {
    Write-Host "[build] smoke launch: $exePath"
    $env:IMAGEMACRO_SKIP_TESSERACT_PROMPT = "1"
    $proc = Start-Process -FilePath $exePath -PassThru
    Start-Sleep -Seconds 6
    if (-not $proc.HasExited) {
        Write-Host "[build] smoke stop process $($proc.Id)"
        Stop-Process -Id $proc.Id -Force
    }
}

Write-Host "[build] done"
Write-Host "[build] artifact: $exePath"
