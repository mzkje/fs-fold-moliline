# Build fs_tool.exe with the C# compiler shipped inside .NET Framework.
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $root "fs_tool.exe"
& $csc /nologo /out:$out (Join-Path $root "fs_tool.cs")
if ($LASTEXITCODE -ne 0) { Write-Error "fs_tool build failed"; exit 1 }
Write-Output "fs_tool built: $out"


