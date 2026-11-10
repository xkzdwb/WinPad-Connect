$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "未找到 csc.exe：$csc" }

$iconArg = "-win32icon:$repo\build\winpad.ico"
$resArg = "-resource:$repo\build\payload.zip,payload.zip"

python "$PSScriptRoot\stage.py"

& $csc -nologo -target:winexe -optimize+ `
    "-out:$repo\build\stage\Win-Pad Connect.exe" `
    -reference:System.Windows.Forms.dll `
    "$repo\installer\Launcher.cs"

& $csc -nologo -target:winexe -optimize+ `
    "-out:$repo\build\stage\Uninstall.exe" `
    -reference:System.Windows.Forms.dll `
    "$repo\installer\Uninstall.cs"

python "$PSScriptRoot\stage.py" --zip

New-Item -ItemType Directory -Force -Path "$repo\dist" | Out-Null
& $csc -nologo -target:winexe -optimize+ `
    $iconArg `
    "-out:$repo\dist\Win-Pad-Connect-Setup-1.0.0.exe" `
    -reference:System.Windows.Forms.dll `
    -reference:System.Drawing.dll `
    -reference:System.IO.Compression.dll `
    -reference:System.IO.Compression.FileSystem.dll `
    $resArg `
    "$repo\installer\Setup.cs"

Write-Host "完成：$repo\dist\Win-Pad-Connect-Setup-1.0.0.exe"
