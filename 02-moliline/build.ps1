# build.ps1 - compile MoliLine v1.0 baseline with Windows built-in csc
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "src"
$bin = Join-Path $root "bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
$targets = @{
  "moli_line_tcp.cs" = "moli_line_tcp.exe";
  "world_svc_tcp.cs" = "world_svc_tcp.exe";
  "world_ctl_tcp.cs" = "world_ctl_tcp.exe";
  "fs_tool.cs" = "fs_tool.exe"
}
foreach ($k in $targets.Keys) {
  $out = Join-Path $bin $targets[$k]
  & $csc /nologo /out:$out (Join-Path $src $k) | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-Error "build failed $k"; exit 1 }
}
Write-Output "BUILD_OK bin=$bin"
# refactor modules & tests
$rf = Join-Path $src "refactor"
$outBus = Join-Path $bin "moli_line_refactor.exe"
& $csc /nologo /out:$outBus (Join-Path $rf "MoliOptions.cs") (Join-Path $rf "WalStore.cs") (Join-Path $rf "BusRegistry.cs") (Join-Path $rf "LeaderElection.cs") (Join-Path $src "MoliWire.cs") (Join-Path $rf "MoliLineRefactor.cs") | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "refactor build failed moli_line_refactor"; exit 1 }
$outA = Join-Path $bin "TestBusRegistry.exe"
& $csc /nologo /out:$outA (Join-Path $rf "BusRegistry.cs") (Join-Path $rf "TestBusRegistry.cs") | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "refactor build failed TestBusRegistry"; exit 1 }
$outB = Join-Path $bin "TestWalStore.exe"
& $csc /nologo /out:$outB (Join-Path $rf "WalStore.cs") (Join-Path $rf "TestWalStore.cs") | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "refactor build failed TestWalStore"; exit 1 }
$outC = Join-Path $bin "TestLeader.exe"
& $csc /nologo /out:$outC (Join-Path $rf "LeaderElection.cs") (Join-Path $rf "TestLeader.cs") | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "refactor build failed TestLeader"; exit 1 }
$outD = Join-Path $bin "TestOptions.exe"
& $csc /nologo /out:$outD (Join-Path $rf "MoliOptions.cs") (Join-Path $rf "TestOptions.cs") | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "refactor build failed TestOptions"; exit 1 }
Write-Output "REFACTOR_BUILD_OK"

