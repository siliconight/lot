# ============================================================
#  night_strip_dress.ps1 (lot v0.18.2) - the art pass over the
#  night strip: Patina procedural PS1 surfacing (delco theme,
#  dressing anchors) + Zoo kit modules + Zoo dressing per store,
#  then the SAME seven frames re-shot for a pure A/B against
#  the graybox run. Fixture gates are untouched (already green).
#
#  Consumes the newest night_strip_<stamp> work dir at the
#  factory root (or pass -Work <dir>). Home: lot\tools\.
#  Run:
#  powershell -ExecutionPolicy Bypass -File C:\Projects\gabagool_studios\gabagool_factory\lot\tools\night_strip_dress.ps1
# ============================================================
param([string]$Work = "", [string]$Skins = "")

$ErrorActionPreference = "Continue"
$LotRepo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Factory = (Resolve-Path (Join-Path $LotRepo "..")).Path
$PatinaRepo = Join-Path $Factory "patina"
$ZooRepo = Join-Path $Factory "zoo"
$LuxProj = Join-Path $Factory "lux"
$Blender = "C:\blender\blender.exe"
$GodotGui = "C:\Godot\4.7\Godot_v4.7-stable_win64.exe"
$GodotCon = "C:\Godot\4.7\Godot_v4.7-stable_win64_console.exe"
$Godot = if (Test-Path $GodotCon) { $GodotCon } else { $GodotGui }

if (-not $Work) {
    $Runs = Join-Path $Factory "_runs"
    $latest = Get-ChildItem @((Join-Path $Runs "night_strip_*"), (Join-Path $Factory "night_strip_*")) -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "dress" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { Write-Host "FATAL: no night_strip_* work dir - run night_strip.ps1 first"; exit 1 }
    $Work = $latest.FullName
}
$Site  = Join-Path $Work "site"
$Dress = Join-Path $Work "dress"
New-Item -ItemType Directory -Path $Dress -Force | Out-Null
$Log = Join-Path $Work "dress.log"

function W([string]$m) { Write-Host $m; Add-Content -Path $Log -Value $m }
function Section([string]$n) { W ""; W ("=" * 62); W ("== " + $n); W ("=" * 62) }
function Run-Godot([string]$label, [string[]]$gargs, [int]$timeoutSec, [bool]$window) {
    $so = Join-Path $Work ($label + "_out.tmp"); $se = Join-Path $Work ($label + "_err.tmp")
    if ($window) { $p = Start-Process -FilePath $Godot -ArgumentList $gargs -PassThru -RedirectStandardOutput $so -RedirectStandardError $se }
    else { $p = Start-Process -FilePath $Godot -ArgumentList $gargs -NoNewWindow -PassThru -RedirectStandardOutput $so -RedirectStandardError $se }
    $null = $p.Handle
    if (-not $p.WaitForExit($timeoutSec * 1000)) { W "  TIMEOUT - killing"; try { $p.Kill() } catch {} }
    $txt = @(); if (Test-Path $so) { $txt += @(Get-Content $so) }; if (Test-Path $se) { $txt += @(Get-Content $se) }
    $txt | Out-File (Join-Path $Work ($label + ".log")) -Encoding utf8
    Remove-Item $so, $se -Force -ErrorAction SilentlyContinue
    W ("  exit=" + $p.ExitCode + " (" + $label + ".log)")
    return ,$txt
}

Section "0. PRE-FLIGHT"
$FixGlb = Get-ChildItem (Join-Path $Work "zoo") -Filter "*_fixtures.glb" -ErrorAction SilentlyContinue | Select-Object -First 1
$SiteLights = Join-Path $Site "out\night_strip.site.lights.json"
foreach ($p in @($Blender, $Godot, $SiteLights)) { if (Test-Path $p) { W ("ok      : " + $p) } else { W ("MISSING : " + $p); exit 1 } }
if (-not $FixGlb) { W "MISSING : fixtures glb (run night_strip.ps1 first)"; exit 1 }
W ("work    : " + $Work)

$stores = @("night_deli", "night_pawn", "night_auto")

if (-not $Skins) {
    $cand = Join-Path $Factory "_runs\skins\delco_signage"
    if (Test-Path (Join-Path $cand "signs_delco")) { $Skins = $cand }
}

if ($Skins) {
    Section "0.5 FIXTURE REBUILD WITH SIGN PACKS (zoo --skins, real Blender)"
    W ("  skins   : " + $Skins)
    Push-Location $ZooRepo
    & $Blender --background --python tools\zoo_cli.py -- --fixtures $SiteLights --theme delco --skins $Skins --out (Join-Path $Work "zoo_skinned") 2>&1 | Out-File (Join-Path $Work "zoo_skinned.log") -Encoding utf8
    W ("  exit=" + $LASTEXITCODE + " (zoo_skinned.log)")
    Pop-Location
    $NewFix = Get-ChildItem (Join-Path $Work "zoo_skinned") -Filter "*_fixtures.glb" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($NewFix) { $FixGlb = $NewFix; W ("  fixtures: " + $FixGlb.Name + " (sign faces branded)") }
    else { W "  WARN: skinned rebuild produced no GLB - keeping the prior fixtures" }
} else {
    W "  (no signage library at _runs\skins\delco_signage - run pixelcoat\tools\make_delco_signage.ps1 for branded signs)"
}

Section "1. PATINA ART PASS x3 (procedural, delco theme, dressing anchors)"
Push-Location $PatinaRepo
foreach ($s in $stores) {
    python -m patina.cli (Join-Path $Site ($s + ".glb")) --mode procedural --theme delco_1997_gas_station --dressing --anchors --seed 1999 --out (Join-Path $Dress ($s + ".patina.glb")) 2>&1 | Select-Object -Last 2 | ForEach-Object { W ("  " + $_) }
    if (-not (Test-Path (Join-Path $Dress ($s + ".patina.glb")))) { W ("FATAL: patina failed for " + $s); Pop-Location; exit 1 }
}
Pop-Location

Section "2. ZOO KIT + DRESSING x3 (real Blender; no --skins: Patina carries surfacing)"
Push-Location $ZooRepo
foreach ($s in $stores) {
    & $Blender --background --python tools\zoo_cli.py -- --build-kit (Join-Path $Site ($s + ".slots.json")) --theme delco --seed 1999 --out $Dress 2>&1 | Out-File (Join-Path $Work ("kit_" + $s + ".log")) -Encoding utf8
    W ("  kit " + $s + " exit=" + $LASTEXITCODE)
    & $Blender --background --python tools\zoo_cli.py -- --dress (Join-Path $Dress ($s + ".patina.dressing.json")) --theme delco --seed 1999 --out $Dress 2>&1 | Out-File (Join-Path $Work ("dressing_" + $s + ".log")) -Encoding utf8
    W ("  dressing " + $s + " exit=" + $LASTEXITCODE)
}
Pop-Location
Get-ChildItem $Dress -Filter "*.glb" | ForEach-Object { W ("  out " + $_.Name + "  " + ("{0:n0}" -f $_.Length)) }

Section "3. STAGE + NIGHT VISUAL PASS (dressed - same 7 frames)"
$Stage = Join-Path $LuxProj "walk\headless"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
Copy-Item $SiteLights -Destination $Stage
Copy-Item $FixGlb.FullName -Destination $Stage
Get-ChildItem $Dress -Filter "*.glb" | ForEach-Object { Copy-Item $_.FullName -Destination $Stage }
Copy-Item (Join-Path $PSScriptRoot "visual_night_strip_dressed.gd") -Destination $Stage
Run-Godot "import_dress" @("--headless","--path",$LuxProj,"--import") 900 $false | Out-Null
$vp = Run-Godot "visual_dress" @("--path",$LuxProj,"--resolution","1920x1080","--script","res://walk/headless/visual_night_strip_dressed.gd") 500 $true
$vp | Where-Object { $_ -match "\[VP\]" } | ForEach-Object { W ("  " + $_) }
$Shots = Join-Path $Stage "shots"
$OutShots = Join-Path $Work "dressed_shots"
New-Item -ItemType Directory -Path $OutShots -Force | Out-Null
if (Test-Path $Shots) { Get-ChildItem $Shots -Filter "*.png" | ForEach-Object { Copy-Item $_.FullName -Destination $OutShots; W ("  shot " + $_.Name) } }

Section "4. PACKAGE"
$Zip = Join-Path (Join-Path $Factory "_runs") ("night_strip_dressed_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".zip")
try { Compress-Archive -Path $OutShots, $Log, (Join-Path $Dress "*.built.json") -DestinationPath $Zip -Force; W ("RESULTS ZIP -> " + $Zip) } catch { W ("zip failed - folder: " + $OutShots) }
W ""
W "Upload the zip - same seven framings as the graybox run, for the A/B."
