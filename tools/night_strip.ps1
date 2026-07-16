# ============================================================
#  night_strip.ps1 (lot v0.18.1) - the DELCO night strip:
#  three DC storefronts (corner_deli / pawn_shop / auto_shop)
#  -> Lot site assemble + lights merge (STREETLIGHTS - the last
#  fixture species without hardware coverage) -> Zoo fixture
#  build (real Blender, all species + LuxEmit markers) -> Lux
#  headless harness (bake + marker gates) -> night visual pass.
#
#  Home: lot\tools\ - paths derive from the repo location.
#  Run:
#  powershell -ExecutionPolicy Bypass -File C:\Projects\gabagool_studios\gabagool_factory\lot\tools\night_strip.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$LotRepo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Factory = (Resolve-Path (Join-Path $LotRepo "..")).Path
$DCRepo  = Join-Path $Factory "deli_counter"
$ZooRepo = Join-Path $Factory "zoo"
$LuxProj = Join-Path $Factory "lux"
$Blender = "C:\blender\blender.exe"
$GodotGui = "C:\Godot\4.7\Godot_v4.7-stable_win64.exe"
$GodotCon = "C:\Godot\4.7\Godot_v4.7-stable_win64_console.exe"
$Godot = if (Test-Path $GodotCon) { $GodotCon } else { $GodotGui }

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Runs  = Join-Path $Factory "_runs"
New-Item -ItemType Directory -Path $Runs -Force | Out-Null
$Work  = Join-Path $Runs ("night_strip_" + $Stamp)
$Site  = Join-Path $Work "site"
New-Item -ItemType Directory -Path $Work, $Site -Force | Out-Null
$Log   = Join-Path $Work "night_strip.log"

function W([string]$m) { Write-Host $m; Add-Content -Path $Log -Value $m }
function Section([string]$n) { W ""; W ("=" * 62); W ("== " + $n); W ("=" * 62) }
function Run-Godot([string]$label, [string[]]$gargs, [int]$timeoutSec, [bool]$window) {
    $so = Join-Path $Work ($label + "_out.tmp"); $se = Join-Path $Work ($label + "_err.tmp")
    W ("  godot " + ($gargs -join " "))
    if ($window) {
        $p = Start-Process -FilePath $Godot -ArgumentList $gargs -PassThru -RedirectStandardOutput $so -RedirectStandardError $se
    } else {
        $p = Start-Process -FilePath $Godot -ArgumentList $gargs -NoNewWindow -PassThru -RedirectStandardOutput $so -RedirectStandardError $se
    }
    $null = $p.Handle
    if (-not $p.WaitForExit($timeoutSec * 1000)) { W "  TIMEOUT - killing"; try { $p.Kill() } catch {} }
    $txt = @(); if (Test-Path $so) { $txt += @(Get-Content $so) }; if (Test-Path $se) { $txt += @(Get-Content $se) }
    $txt | Out-File (Join-Path $Work ($label + ".log")) -Encoding utf8
    Remove-Item $so, $se -Force -ErrorAction SilentlyContinue
    W ("  exit=" + $p.ExitCode + " (" + $label + ".log)")
    return ,$txt
}

Section "0. PRE-FLIGHT"
foreach ($p in @($Blender, $Godot, (Join-Path $DCRepo "new_level.py"), (Join-Path $LuxProj "project.godot"))) {
    if (Test-Path $p) { W ("ok      : " + $p) } else { W ("MISSING : " + $p); exit 1 }
}

Section "1. DC STOREFRONTS x3 (real Blender)"
$stores = @(
    @{ preset = "corner_deli"; name = "night_deli" },
    @{ preset = "pawn_shop";   name = "night_pawn" },
    @{ preset = "auto_shop";   name = "night_auto" }
)
Push-Location $DCRepo
foreach ($s in $stores) {
    W ("  -- " + $s.preset + " -> " + $s.name)
    python new_level.py --preset $s.preset --name $s.name --mode heist --force 2>&1 | Select-Object -Last 2 | ForEach-Object { W ("     " + $_) }
    python build.py (Join-Path "specs" ($s.name + ".json")) --out (Join-Path $Site ($s.name + ".glb")) --blender $Blender 2>&1 | Select-Object -Last 3 | ForEach-Object { W ("     " + $_) }
    if (-not (Test-Path (Join-Path $Site ($s.name + ".lights.json")))) { W ("FATAL: " + $s.name + " lights manifest missing"); Pop-Location; exit 1 }
    $m = Get-Content (Join-Path $Site ($s.name + ".lights.json")) -Raw | ConvertFrom-Json
    $types = ($m.anchors | Group-Object type | ForEach-Object { $_.Name + " x " + $_.Count }) -join ", "
    W ("     anchors: " + $types)
}
Pop-Location

Section "2. LOT SITE ASSEMBLE + LIGHTS MERGE (streetlights derived)"
Copy-Item (Join-Path $LotRepo "specs\night_strip.site.json") -Destination $Site
Push-Location $LotRepo
python lot.py (Join-Path $Site "night_strip.site.json") (Join-Path $Site "out") --walkable 2>&1 | Select-Object -Last 8 | ForEach-Object { W ("  " + $_) }
Pop-Location
$SiteLights = Join-Path $Site "out\night_strip.site.lights.json"
if (-not (Test-Path $SiteLights)) { W "FATAL: site lights merge missing"; exit 1 }
$sm = Get-Content $SiteLights -Raw | ConvertFrom-Json
$stypes = ($sm.anchors | Group-Object type | ForEach-Object { $_.Name + " x " + $_.Count }) -join ", "
W ("  site anchors: " + $stypes)

Section "3. ZOO FIXTURE BUILD (real Blender, ALL species incl. streetlight)"
Push-Location $ZooRepo
& $Blender --background --python tools\zoo_cli.py -- --fixtures $SiteLights --theme delco --out (Join-Path $Work "zoo") 2>&1 | Out-File (Join-Path $Work "zoo_build.log") -Encoding utf8
W ("  exit=" + $LASTEXITCODE + " (zoo_build.log)")
Pop-Location
$FixIdx = Get-ChildItem (Join-Path $Work "zoo") -Filter "*_fixtures.built.json" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $FixIdx) { W "FATAL: no fixtures index - see zoo_build.log"; exit 1 }
$fi = Get-Content $FixIdx.FullName -Raw | ConvertFrom-Json
W ("  built: " + ($fi.counts | ConvertTo-Json -Compress) + "  emitter_markers=" + $fi.emitter_markers)
$FixGlb = Get-ChildItem (Join-Path $Work "zoo") -Filter "*_fixtures.glb" | Select-Object -First 1

Section "4. LUX HEADLESS HARNESS (bake + marker gates, incl. LuxStreetlightRig)"
$Stage = Join-Path $LuxProj "walk\headless"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
Copy-Item $SiteLights -Destination $Stage
Copy-Item $FixGlb.FullName -Destination $Stage
Run-Godot "import1" @("--headless","--path",$LuxProj,"--import") 900 $false | Out-Null
$hw = Run-Godot "harness" @("--headless","--path",$LuxProj,"--script","res://tools/walk_harness.gd") 600 $false
$hw | Where-Object { $_ -match "\[HW" } | ForEach-Object { W ("  " + $_) }
foreach ($f in @("headless_report.json","headless_walk.tscn")) {
    $p = Join-Path $Stage $f
    if (Test-Path $p) { Copy-Item $p -Destination $Work; W ("  collected " + $f) }
}

Section "5. NIGHT VISUAL PASS (windowed - a Godot window will appear)"
foreach ($s in $stores) { Copy-Item (Join-Path $Site ($s.name + ".glb")) -Destination $Stage }
Copy-Item (Join-Path $PSScriptRoot "visual_night_strip.gd") -Destination $Stage
Run-Godot "import2" @("--headless","--path",$LuxProj,"--import") 900 $false | Out-Null
$vp = Run-Godot "visual" @("--path",$LuxProj,"--resolution","1920x1080","--script","res://walk/headless/visual_night_strip.gd") 400 $true
$vp | Where-Object { $_ -match "\[VP\]" } | ForEach-Object { W ("  " + $_) }
$Shots = Join-Path $Stage "shots"
if (Test-Path $Shots) { Get-ChildItem $Shots -Filter "*.png" | ForEach-Object { Copy-Item $_.FullName -Destination $Work; W ("  shot " + $_.Name) } }

Section "6. PACKAGE"
$Zip = Join-Path $Runs ("night_strip_" + $Stamp + ".zip")
try { Compress-Archive -Path (Join-Path $Work "*") -DestinationPath $Zip -Force; W ("RESULTS ZIP -> " + $Zip) } catch { W ("zip failed - folder: " + $Work) }
W ""
W "Upload the zip. Walkable scene: site\out\night_strip_walk.tscn (open in the"
W "Lot Godot project or import into lux) - drop the fixtures GLB beside it."
