# ============================================================
#  walk_night_strip.ps1 (lot v0.18.5) - walk the night strip in
#  first person. Uses whatever the dress run staged in the lux
#  project; completes missing pieces from the newest run dirs
#  under _runs (prefers the BRANDED fixtures from zoo_skinned).
#
#    WASD move | SHIFT sprint | SPACE jump | F power cut
#    G cycle grade | ESC release mouse | F8 quit
#
#  Home: lot\tools\.  Run:
#  powershell -ExecutionPolicy Bypass -File C:\Projects\gabagool_studios\gabagool_factory\lot\tools\walk_night_strip.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$LotRepo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Factory = (Resolve-Path (Join-Path $LotRepo "..")).Path
$LuxProj = Join-Path $Factory "lux"
$GodotGui = "C:\Godot\4.7\Godot_v4.7-stable_win64.exe"
$GodotCon = "C:\Godot\4.7\Godot_v4.7-stable_win64_console.exe"
$Godot = if (Test-Path $GodotCon) { $GodotCon } else { $GodotGui }
$Stage = Join-Path $LuxProj "walk\headless"
New-Item -ItemType Directory -Path $Stage -Force | Out-Null

function Find-Run([string]$pattern) {
    Get-ChildItem @((Join-Path $Factory "_runs\$pattern"), (Join-Path $Factory $pattern)) -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "dress" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

# -- complete the staging (dress run usually left everything in place) --
$run = Find-Run "night_strip_*"
if (-not (Get-ChildItem $Stage -Filter "*.lights.json" -ErrorAction SilentlyContinue)) {
    if ($run) { Copy-Item (Join-Path $run.FullName "site\out\night_strip.site.lights.json") -Destination $Stage -ErrorAction SilentlyContinue }
}
$haveFix = Get-ChildItem $Stage -Filter "*_fixtures.glb" -ErrorAction SilentlyContinue
if ($run) {
    $branded = Get-ChildItem (Join-Path $run.FullName "zoo_skinned") -Filter "*_fixtures.glb" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($branded) { Copy-Item $branded.FullName -Destination $Stage -Force; Write-Host ("fixtures: " + $branded.Name + " (branded)") }
    elseif (-not $haveFix) {
        $plain = Get-ChildItem (Join-Path $run.FullName "zoo") -Filter "*_fixtures.glb" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($plain) { Copy-Item $plain.FullName -Destination $Stage; Write-Host ("fixtures: " + $plain.Name) }
    }
    foreach ($s in "night_deli","night_pawn","night_auto") {
        $pat = Join-Path $run.FullName "dress\$s.patina.glb"
        $raw = Join-Path $run.FullName "site\$s.glb"
        $dres = Join-Path $run.FullName "dress\${s}_dressing.glb"
        if ((Test-Path $pat) -and -not (Test-Path (Join-Path $Stage "$s.patina.glb"))) { Copy-Item $pat -Destination $Stage }
        elseif ((Test-Path $raw) -and -not (Test-Path (Join-Path $Stage "$s.glb")) -and -not (Test-Path (Join-Path $Stage "$s.patina.glb"))) { Copy-Item $raw -Destination $Stage }
        if ((Test-Path $dres) -and -not (Test-Path (Join-Path $Stage "${s}_dressing.glb"))) { Copy-Item $dres -Destination $Stage }
    }
}
Copy-Item (Join-Path $PSScriptRoot "walk_night_strip.gd") -Destination $Stage -Force

Write-Host "staged:"
Get-ChildItem $Stage -Include "*.glb","*.lights.json","walk_night_strip.gd" -Recurse -Name | ForEach-Object { Write-Host ("  " + $_) }

Write-Host "importing..."
& $Godot --headless --path $LuxProj --import 2>&1 | Out-Null
Write-Host "launching (WASD | SHIFT | SPACE | F power cut | G grade | ESC | F8 quit)"
& $GodotGui --path $LuxProj --resolution 1920x1080 --script res://walk/headless/walk_night_strip.gd
