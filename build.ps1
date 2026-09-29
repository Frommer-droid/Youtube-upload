# Build and verify the Windows onedir release from the project virtual environment.
$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$python = Join-Path $root '.venv\Scripts\python.exe'
$spec = Join-Path $root 'Build_Tools\YouTubePrivateUploader.spec'
$work = Join-Path $root 'Build_Tools\build'
$dist = Join-Path $root 'Build_Tools\dist'
$app = Join-Path $root 'YouTubePrivateUploader'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project .venv Python is missing: $python"
}
$savedPath = $env:PATH
try {
    $trustedPath = & $python (Join-Path $root 'Build_Tools\native_runtime.py') --python $python
    if ($LASTEXITCODE -ne 0 -or -not $trustedPath) { throw 'Trusted runtime PATH setup failed' }
    $env:PATH = $trustedPath
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:PYTHONDONTWRITEBYTECODE = '1'

    & $python -m pytest tests -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    & $python -m ruff check src tests Build_Tools --no-cache
    if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }

    # The root output must be removed before invoking PyInstaller.
    $expected = [System.IO.Path]::GetFullPath((Join-Path $root 'YouTubePrivateUploader'))
    if ([System.IO.Path]::GetFullPath($app) -ne $expected -or
        [System.IO.Path]::GetDirectoryName($expected) -ne $root) {
        throw "Unexpected build output path: $app"
    }
    if (Test-Path -LiteralPath $app) {
        $item = Get-Item -LiteralPath $app -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing to remove a reparse point: $app"
        }
        Remove-Item -LiteralPath $app -Recurse -Force
    }

    & $python -m PyInstaller $spec --clean --noconfirm --distpath $dist --workpath $work
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    $toc = @(Get-ChildItem -LiteralPath $work -Filter 'COLLECT-00.toc' -Recurse -File)
    if ($toc.Count -ne 1) { throw "Expected one COLLECT-00.toc; found $($toc.Count)" }
    & $python (Join-Path $root 'Build_Tools\audit_collect.py') $toc[0].FullName
    if ($LASTEXITCODE -ne 0) { throw 'COLLECT native runtime audit failed' }
    & $python (Join-Path $root 'Build_Tools\post_build.py')
    if ($LASTEXITCODE -ne 0) { throw 'Post-build failed' }
    & $python (Join-Path $root 'Build_Tools\frozen_smoke.py') (Join-Path $app 'YouTubePrivateUploader.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Frozen smoke failed' }
    Write-Host "Verified build: $app"
}
finally {
    $env:PATH = $savedPath
}
