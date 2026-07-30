extends Node3D
## heist_nav_qa / nav_qa_director.gd -- the automated walktest bot (Godot 4)
## ----------------------------------------------------------------------------
## The addon Lot's *_navqa.tscn has always fed (see lot_navqa_setup.gd) --
## this is its first shipped implementation. Two passes over the baked site
## navmesh, then a verdict:
##
##   PASS 1 -- PATH PROOFS (exhaustive, instant): from the crew home to every
##   player proxy (crew spawn / objective / loot / extraction), and between
##   consecutive proxies (the mission spine: spawn -> objective ->
##   extraction), prove a navmesh path exists AND both endpoints snap onto
##   the mesh. An off-mesh anchor is a landing/courtyard that didn't bake --
##   exactly the failure a human walktest finds.
##
##   PASS 2 -- SIMULATED WALKERS (physical, timed): spawn `simulated_players`
##   CharacterBody3D agents at the crew home and drive them along the mission
##   spine with NavigationAgent3D + move_and_slide under real physics. A
##   walker that stops progressing for STUCK_SECS is STUCK -- the collision
##   trap class that pure path queries cannot see. `bot_count` extra walkers
##   run bot_spawn -> nearest proxy legs for pressure-route coverage.
##
## Interface matches lot_navqa_setup.gd exactly: exported groups + counts,
## run_on_ready, start_qa_run(). Headless (DisplayServer "headless") it writes
## <scene>.walktest.json next to the project and quits 0/1; in the editor it
## just prints and leaves the scene running.

@export var simulated_players: int = 4
@export var bot_count: int = 16
@export var player_proxy_group: String = "navqa_player_proxy"
@export var cover_group: String = "navqa_cover"
@export var bot_spawn_group: String = "navqa_bot_spawn"
@export var run_on_ready: bool = true

# QA metrics from the shared agent contract via the runner's env bridge
# (DC_QA_* / DC_NAV_*); fallbacks equal the ratified values.
static func _envf(key: String, fallback: float) -> float:
	var v := OS.get_environment(key)
	return float(v) if v != "" else fallback

var AGENT_RADIUS := _envf("DC_NAV_RADIUS", 0.4)
var AGENT_HEIGHT := _envf("DC_NAV_HEIGHT", 1.8)
var SNAP_MAX := _envf("DC_QA_SNAP", 2.0)
var WALK_SPEED := 4.0            # m/s
var STUCK_SECS := _envf("DC_QA_STUCK", 4.0)
const TIME_LIMIT := 120.0        # hard cap on the simulation (seconds)
const MAX_REPATHS := 3           # per-leg fresh-path retries before "stuck"
const STEP_UP := 0.5             # agent_contract characters.player.max_step_up_m
const STEP_FWD := 0.35           # forward probe when stepping (≈ capsule radius)
var ARRIVE_DIST := _envf("DC_QA_ARRIVE", 1.5)
#: How close counts as HAVING REACHED a path waypoint. Not ARRIVE_DIST -- that
#: one is for leg targets. This was a hardcoded 0.6, which is wider than the
#: lateral correction a funnelled path asks for at a corner: on
#: warehouse_district the corner waypoint sat 0.45 m away, inside 0.6, so it was
#: consumed while the body was still on the wrong side of the corner and the
#: body then steered at the far waypoint straight into a wall. Bounded by the
#: body instead of chosen. The margin available is exactly
#: (nav agent radius after voxel ceiling) - (this body's radius): the funnel
#: offsets a corner waypoint by the radius the map was BAKED for, and the body
#: only needs its own. On warehouse_district that is 0.45 - 0.28 = 0.17, so a
#: consume radius above 0.17 eats the clearance and the body clips the corner.
#: Simulated against the real wall from the .glb: 0.60 hits it (which is the
#: shipped behaviour and the observed failure), 0.30 still hits it, 0.15 clears.
#: NOTE this margin VANISHES if the walker is widened to the bake radius --
#: see clearances in agent_contract.json before raising the body.
#: Derived, not chosen. The funnel offsets a corner waypoint by the radius the
#: map was BAKED for and the body only needs its own, so the clearance a corner
#: gives us is (bake radius) - (walker radius). This walker is AGENT_RADIUS *
#: 0.7, making the margin 0.3 * AGENT_RADIUS, and 60% of that leaves room for
#: the step the body takes between frames. Two measured points agree: at
#: cell_size 0.15 the bake radius ceiled to 0.45 (margin 0.17) and 0.15 worked;
#: at cell_size 0.10 it is 0.40 exactly (margin 0.12) and 0.15 CLIPPED while
#: 0.07 cleared. Uses the un-ceiled radius because the director cannot see
#: cell_size, and ceiling only ever widens the real margin -- so this is the
#: conservative reading at any grid size.
var WP_RADIUS := _envf("DC_QA_WP", AGENT_RADIUS * 0.18)

var _report := {}
var _walkers: Array = []
#: anchor name -> true, for anchors that are NOT on the largest cluster.
var _stranded_names := {}
#: raw anchor position -> the standing position the census settled on.
var _resolved := {}
#: What _drive records on a walker that gives up, and _conclude must copy into
#: the report. _conclude built its entry from a fixed list of five keys, so
#: 0.30.0 captured every slide collision the stuck capsule was touching and then
#: dropped all of it on the way out -- the library sweep came back with
#: `blocked_by` absent on all three failing sites, from a director that had
#: measured it. A serializer with a hand-written key list silently discards
#: whatever is added later, which is the same defect as the instrument that
#: measures the wrong thing, one layer further out.
const WALKER_DIAGNOSTIC_KEYS := ["blocked_by", "waypoint", "waypoint_dist_m",
	"path_index", "path_points", "on_floor", "on_wall", "step_fail"]
var _sim_time := 0.0
var _time_limit := TIME_LIMIT     # scaled to the spine after the proofs run
var _done := false


func _ready() -> void:
	# _physics_process is enabled by default the moment the node enters the
	# tree -- which let _conclude race ahead of _run. Nothing ticks until
	# _run arms it explicitly.
	set_physics_process(false)
	if run_on_ready:
		start_qa_run()


func start_qa_run() -> void:
	# wait for the nav bake + NavigationServer sync: the site bake takes
	# real seconds, and querying an unsynced map snaps everything to the
	# world origin. Poll the map's iteration id (0 = never synced).
	var map: RID = get_world_3d().navigation_map
	var tries := 0
	while NavigationServer3D.map_get_iteration_id(map) == 0 and tries < 1800:
		await get_tree().physics_frame
		tries += 1
	await get_tree().physics_frame
	if tries >= 1800:
		print("[nav-qa] WARNING: navigation map never synced (30 s) -- "
			+ "proofs will fail honestly")
	_run()


func _run() -> void:
	var map: RID = get_world_3d().navigation_map
	NavigationServer3D.map_force_update(map)
	var regions := NavigationServer3D.map_get_regions(map)
	print("[nav-qa] map: %d region(s), iteration %d" % [regions.size(),
		NavigationServer3D.map_get_iteration_id(map)])
	var origin_probe := NavigationServer3D.map_get_closest_point(map,
		global_position)
	if origin_probe == Vector3.ZERO \
			and global_position.distance_to(Vector3.ZERO) > 2.0:
		# async commit may still be settling: retry for up to 10 s
		var retry := 0
		while origin_probe == Vector3.ZERO and retry < 600:
			await get_tree().physics_frame
			NavigationServer3D.map_force_update(map)
			origin_probe = NavigationServer3D.map_get_closest_point(map,
				global_position)
			retry += 1
		print("[nav-qa] map probe settled after %d frame(s)" % retry)
	if regions.is_empty() or (origin_probe == Vector3.ZERO
			and global_position.distance_to(Vector3.ZERO) > 2.0):
		_report = {"ok": false, "error": "navigation map is EMPTY at QA time "
			+ "(bake produced no polygons or region never registered)",
			"regions": regions.size()}
		_finish(false)
		return
	var proxies := _group_points(player_proxy_group)
	var bot_spawns := _group_points(bot_spawn_group)
	var home := global_position

	_report = {"ok": false, "path_proofs": [], "walkers": [],
			   "proxies": proxies.size(), "bot_spawns": bot_spawns.size(),
			   "map_iteration": NavigationServer3D.map_get_iteration_id(map)}

	if proxies.is_empty():
		_report["error"] = "no player proxies in group '%s'" % player_proxy_group
		_finish(false)
		return

	# ---- pass 0: is each anchor standing on anything that GOES anywhere? ---
	#
	# `_prove_path` already refuses an anchor further than SNAP_MAX from the
	# mesh, and that check is not the one that was missing: on the run that
	# started this, every anchor passed it and nine legs still failed. An anchor
	# 0.7 m from a two-polygon scrap is ON the navmesh and goes nowhere, and a
	# leg failing from there reported "disjoint islands" -- a true statement
	# about the navmesh that reads as a claim about the whole site rather than
	# about one endpoint. Four instruments disagreed for a day over it.
	#
	# So measure connectivity, not just proximity, using the same API the proof
	# uses. Anchors x anchors is 400 queries at twenty anchors; the walker sim
	# that follows costs 230 seconds.
	_report["anchors"] = _anchor_reachability(map, home, proxies)
	var stranded := 0
	var no_room := 0
	var behind_barrier := 0
	for a in _report["anchors"]:
		if float(a.get("unreachable_stand_m", 0.0)) > 0.0:
			behind_barrier += 1
			print("[nav-qa] %s: nearest standing room (%.2f m) is on a component nothing reaches; using the nearest CONNECTED one at %.2f m -- the marker is behind something no body walks through"
				% [a["name"], float(a["unreachable_stand_m"]), a["snap_m"]])
		if bool(a.get("no_standing_room", false)):
			no_room += 1
			print("[nav-qa] %s: NO STANDING ROOM on its own storey within %.0f m of (%.1f, %.1f, %.1f) -- that room did not bake"
				% [a["name"], STAND_SEARCH_M, a["raw"][0], a["raw"][1],
				   a["raw"][2]])
			continue
		if int(a["cluster_size"]) < int(a["main_cluster_size"]):
			stranded += 1
			print("[nav-qa] %s: OFF THE MAIN NETWORK -- stands %.2f m away at (%.1f, %.1f, %.1f), cluster of %d vs main %d"
				% [a["name"], a["snap_m"], a["snap"][0], a["snap"][1],
				   a["snap"][2], int(a["cluster_size"]),
				   int(a["main_cluster_size"])])
	_report["stranded_anchors"] = stranded
	_report["anchors_without_standing_room"] = no_room
	_report["anchors_behind_a_barrier"] = behind_barrier

	# ---- pass 1: path proofs ----------------------------------------------
	var proof_fail := 0
	var legs: Array = []
	for i in proxies.size():
		legs.append(["home->proxy_%d" % i, home, proxies[i]])
	for i in range(proxies.size() - 1):
		legs.append(["proxy_%d->proxy_%d" % [i, i + 1],
					 proxies[i], proxies[i + 1]])
	for leg in legs:
		var rep := _prove_path(map, leg[0], leg[1], leg[2])
		# A leg from or to a stranded anchor is not evidence about the route --
		# it is the anchor, restated. Say which, so the reader does not go
		# looking at the navmesh for a defect that is in the placement.
		if not rep["ok"]:
			var blame := _stranded_blame(leg[0])
			if blame != "":
				rep["isolated_endpoint"] = blame
				rep["detail"] = "%s is off the main network; %s" \
					% [blame, rep["detail"]]
		_report["path_proofs"].append(rep)
		if not rep["ok"]:
			proof_fail += 1
		print("[nav-qa] %s: %s -- %s" % [leg[0],
			"ok" if rep["ok"] else "FAIL", rep["detail"]])

	# players walk home -> p0 -> p1 -> ...: size the sim clock to that spine
	# (the hero site's 18-target spine ran the fixed 120 s cap out at exactly
	# WALK_SPEED x 120 travelled -- a capacity limit, not a nav failure)
	var spine_m := 0.0
	for rep2 in _report["path_proofs"]:
		var lbl: String = rep2["leg"]
		if lbl == "home->proxy_0" or (lbl.begins_with("proxy_") and "->" in lbl):
			spine_m += float(rep2.get("length_m", 25.0))
	_time_limit = clampf(spine_m / WALK_SPEED * 2.0 + 30.0, TIME_LIMIT, 600.0)
	print("[nav-qa] spine ~%.0f m -> sim cap %.0f s" % [spine_m, _time_limit])

	# ---- pass 2: simulated walkers ----------------------------------------
	var spine: Array = [home]
	for p in proxies:
		spine.append(p)
	for i in maxi(simulated_players, 1):
		_spawn_walker("player_%d" % i, home + Vector3(i * 1.6, 0.5, 0.0),
					  spine.slice(1))
	for i in mini(bot_count, bot_spawns.size() * 4):
		var s: Vector3 = bot_spawns[i % maxi(bot_spawns.size(), 1)] \
			if not bot_spawns.is_empty() else home
		var tgt: Variant = _nearest_reachable(map, proxies, s)
		if tgt == null:
			_walkers.append({"name": "bot_%d" % i, "body": null,
							 "targets": [], "ti": 0, "reached": 0,
							 "travelled": 0.0, "last_pos": s, "stall": 0.0,
							 "finished": true,
							 "status": "ok_vertical_targets_only"})
			continue
		_spawn_walker("bot_%d" % i, s + Vector3(0, 0.5, 0), [tgt])

	_report["_proof_failures"] = proof_fail
	set_physics_process(true)


func _physics_process(delta: float) -> void:
	if _done or _walkers.is_empty():
		return
	_sim_time += delta
	var all_done := true
	for w in _walkers:
		if not w["finished"]:
			_drive(w, delta)
			all_done = all_done and w["finished"]
	if all_done or _sim_time > _time_limit:
		_conclude()


func _conclude() -> void:
	_done = true
	set_physics_process(false)
	var walk_fail := 0
	for w in _walkers:
		var rep := {"name": w["name"], "status": w["status"],
					"targets_reached": w["reached"],
					"targets_total": w["targets"].size(),
					"travelled_m": snappedf(w["travelled"], 0.1)}
		for k in WALKER_DIAGNOSTIC_KEYS:
			if w.has(k):
				rep[k] = w[k]
		var suffix := ""
		if w.has("at"):
			rep["at"] = w["at"]
		if w.get("body") != null and not w["finished"]:
			# ran out the clock -- record WHERE, so a timeout is debuggable
			var p: Vector3 = (w["body"] as CharacterBody3D).global_position
			rep["at"] = [snappedf(p.x, 0.1), snappedf(p.y, 0.1), snappedf(p.z, 0.1)]
			suffix = " at (%.1f, %.1f, %.1f)" % [p.x, p.y, p.z]
		_report["walkers"].append(rep)
		# every ok-flavored status passes: "ok", "ok(1 vertical leg(s)...)",
		# "ok_vertical_targets_only" -- exact match rejected the vertical ones
		if not (w["status"] as String).begins_with("ok"):
			walk_fail += 1
		print("[nav-qa] walker %s: %s (%d/%d targets, %.1f m)%s"
			% [w["name"], w["status"], w["reached"], w["targets"].size(),
			   w["travelled"], suffix])
	var ok: bool = int(_report.get("_proof_failures", 1)) == 0 and walk_fail == 0
	_finish(ok)


func _finish(ok: bool) -> void:
	_report["ok"] = ok
	_report["sim_seconds"] = snappedf(_sim_time, 0.1)
	print("[nav-qa] verdict: %s" % ("PASS" if ok else "FAIL"))
	if DisplayServer.get_name() == "headless":
		var scene_file := get_tree().current_scene.scene_file_path
		var out := scene_file.get_basename() + ".walktest.json" \
			if scene_file != "" else "res://walktest.json"
		var f := FileAccess.open(out, FileAccess.WRITE)
		if f:
			f.store_string(JSON.stringify(_report, "  "))
			f.close()
			print("[nav-qa] wrote %s" % ProjectSettings.globalize_path(out))
		get_tree().quit(0 if ok else 1)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

func _nearest_reachable(map: RID, points: Array, from_pos: Vector3) -> Variant:
	## nearest proxy a walkable path actually reaches; null when every
	## candidate is vertical-access only (ladder territory -- intel)
	var order := points.duplicate()
	order.sort_custom(func(a, b):
		return from_pos.distance_to(a) < from_pos.distance_to(b))
	var sa := _snap(map, from_pos)
	for pt in order:
		var v: Vector3 = pt
		var sb := _snap(map, v)
		var path := NavigationServer3D.map_get_path(map, sa, sb, true)
		if path.size() >= 2 \
				and path[path.size() - 1].distance_to(sb) <= SNAP_MAX:
			return v
	return null


func _nearest(points: Array, to: Vector3) -> Vector3:
	var best := to
	var best_d := INF
	for pt in points:
		var v: Vector3 = pt
		var d := to.distance_to(v)
		if d < best_d:
			best_d = d
			best = v
	return best


func _group_points(group: String) -> Array:
	var pts: Array = []
	for n in get_tree().get_nodes_in_group(group):
		if n is Node3D:
			pts.append((n as Node3D).global_position)
	return pts


#: How far ABOVE its own floor a standing position may be found: one max_climb
#: plus a bake voxel, and no more. Downward the allowance is a body height --
#: see _stand_at for why the two directions are not the same question.
const STOREY_BAND := 0.6
#: How far sideways to look for standing room, and at what granularity.
const STAND_SEARCH_M := 6.0
const STAND_STEP_M := 0.5
const STAND_DIRS := 12


func _stand_at(map: RID, q: Vector3, plane_y: float) -> Variant:
	## Navmesh nearest the short vertical segment at `q`, if it lies on the
	## anchor's own storey. null when this sample finds nothing on that plane.
	var c := NavigationServer3D.map_get_closest_point_to_segment(
		map, q + Vector3(0.0, STOREY_BAND, 0.0),
		q - Vector3(0.0, AGENT_HEIGHT, 0.0), false)
	# map_get_closest_point* answers Vector3.ZERO when it has nothing to say.
	# Only the world origin can legitimately be that answer.
	if c == Vector3.ZERO and q.distance_to(Vector3.ZERO) > STAND_STEP_M:
		return null
	# Asymmetric on purpose. BELOW the anchor by up to a body height is still
	# this storey -- crew_home carries a 1.0 m lift and an unroomed marker still
	# carries Deli Counter's 0.9 m body height. ABOVE the anchor is a different
	# surface: that direction is how a counter top at 1.4 m came to stand in for
	# the floor at 0.2, and it stays shut to within a bake voxel.
	if c.y > plane_y + STOREY_BAND or c.y < plane_y - AGENT_HEIGHT:
		return null
	# The sample owns its neighbourhood: a point further out than the ring
	# spacing belongs to some other sample, and taking it here would let one
	# lucky direction stand in for a sweep that never happened.
	if Vector2(c.x - q.x, c.z - q.z).length() > STAND_STEP_M:
		return null
	return c


func _snap(map: RID, p: Vector3) -> Vector3:
	var pt: Vector3 = _stand_point(map, p)["point"]
	return pt


func _key(p: Vector3) -> String:
	return "%.2f,%.2f,%.2f" % [p.x, p.y, p.z]


func _stand_point(map: RID, p: Vector3) -> Dictionary:
	# The census resolves anchors whose nearest standing room is on a component
	# nothing reaches. Every later consumer -- the path proofs, the walker legs,
	# the bot target search -- has to use the same answer, or the report grades
	# routes to a position the census already ruled out. One cache, one answer.
	if _resolved.has(_key(p)):
		return _resolved[_key(p)]
	return _stand_search(map, p)


func _stand_search(map: RID, p: Vector3) -> Dictionary:
	## Where does a body stand to use the thing at `p`? On the floor of p's own
	## storey -- beside it if need be, never above it.
	##
	## map_get_closest_point is omnidirectional, and that is the wrong question
	## for a standing position. Two earlier versions of this asked it anyway and
	## the reports were wrong in two different ways. A marker is where a thing
	## IS: Deli Counter puts OBJECTIVE_CAGE on the cashier counter and
	## LOOT_VAULT_CASH inside an 8 x 6 m vault block. The floor directly under
	## those markers is inside a solid prop, so the nearest navmesh in any
	## direction is the prop's own tabletop -- a 1.0 m surface no body can climb
	## to, which bakes as an isolated island. Sixteen of twenty-one anchors
	## snapped onto furniture and the report read as a severed navmesh.
	##
	## Lot now emits anchors at their room's floor, so the storey is known: search
	## that plane outward for the first place a body fits. A vault marker resolves
	## to the floor at the vault's edge, which is where a player stands to open it.
	var plane_y := p.y
	var here = _stand_at(map, p, plane_y)
	if here != null:
		var hv: Vector3 = here
		return {"point": hv, "offset": hv.distance_to(p), "found": true}
	var r := STAND_STEP_M
	while r <= STAND_SEARCH_M:
		# Ring density follows the radius. A fixed count leaves 3 m arc gaps at
		# 6 m, and every sample only speaks for STAND_STEP_M around itself, so a
		# fixed count would report "no standing room" for floor it never sampled.
		var dirs := maxi(STAND_DIRS, int(ceil(TAU * r / STAND_STEP_M)))
		var best := Vector3.ZERO
		var best_d := INF
		for k in dirs:
			var a := TAU * float(k) / float(dirs)
			var c = _stand_at(map, p + Vector3(cos(a) * r, 0.0, sin(a) * r), plane_y)
			if c == null:
				continue
			var cv: Vector3 = c
			var d := cv.distance_to(p)
			if d < best_d:
				best_d = d
				best = cv
		if best_d < INF:
			return {"point": best, "offset": best_d, "found": true}
		r += STAND_STEP_M
	# No standing room anywhere on this storey within STAND_SEARCH_M -- the room
	# this anchor names did not bake. Return the anchor itself and say so rather
	# than resolving to a position on some other floor that no body can use.
	return {"point": p, "offset": 0.0, "found": false}


func _reaches(map: RID, from_snapped: Vector3, to_snapped: Vector3,
			  strict: bool = false) -> bool:
	## Can a walkable route get from one snapped anchor to another?
	##
	## `strict` drops the vertical-access concession. Clustering uses it, and
	## has to: a 2.9 m drop onto a tabletop satisfied the concession in both
	## directions, so union-find glued every furniture island to the floor and
	## reported "one cluster of 21, 0 stranded" on a run where sixteen anchors
	## could not be walked to. A drop is not a two-way edge and must not join
	## two components. Legs keep the concession -- a ladder is real access, and
	## _prove_path says which kind it found.
	var path := NavigationServer3D.map_get_path(map, from_snapped, to_snapped, true)
	if path.size() < 2:
		return false
	var pe: Vector3 = path[path.size() - 1]
	if pe.distance_to(to_snapped) <= SNAP_MAX:
		return true
	if strict:
		return false
	var h_gap := Vector2(pe.x - to_snapped.x, pe.z - to_snapped.z).length()
	var v_gap := absf(pe.y - to_snapped.y)
	return h_gap <= SNAP_MAX * 1.5 and v_gap > 1.0


func _anchor_reachability(map: RID, home: Vector3, proxies: Array) -> Array:
	## For every anchor: where it snapped, how far, and how many OTHER anchors
	## it can actually reach. Zero is the number that matters -- an anchor on a
	## scrap passes every distance check and can never appear in a route.
	var names: Array = ["home"]
	var pts: Array = [home]
	for i in proxies.size():
		names.append("proxy_%d" % i)
		pts.append(proxies[i])

	_resolved = {}
	var snapped: Array = []
	var no_room: Array = []
	var offsets: Array = []
	var rerouted: Array = []
	for p in pts:
		var pv: Vector3 = p
		var info := _stand_search(map, pv)
		snapped.append(info["point"])
		offsets.append(float(info["offset"]))
		no_room.append(not bool(info["found"]))
		rerouted.append(0.0)

	var out := _census(map, names, pts, snapped, offsets, no_room, rerouted)

	# ---- second pass: the nearest standing room is not always a standing
	# position a player can ever occupy ----------------------------------------
	#
	# A marker on the wrong side of something nothing walks through resolves to
	# a floor no route reaches. The vault is the case that forced this: Deli
	# Counter divides the basement with a full-height wall whose only opening is
	# a reinforced concrete breach panel, and it puts LOOT_VAULT_CASH inside a
	# vault block that straddles that wall. The two sides are within a few
	# centimetres of each other in distance from the marker, so which side the
	# ring search picked was a tie-break -- and one or two vaults per seed came
	# out stranded while the rest passed, on identical geometry.
	#
	# Asking for the nearest CONNECTED standing room settles it, and settles it
	# correctly rather than arbitrarily: for a sealed room that is the floor
	# outside its door, which is where a player stands to breach. The bound is
	# the same STAND_SEARCH_M as the first pass, so this cannot walk an anchor
	# across a site, and both distances are reported.
	var main_ref := _main_reference(out)
	var moved := false
	if main_ref >= 0:
		for i in pts.size():
			if int(out[i]["cluster_size"]) >= int(out[i]["main_cluster_size"]):
				continue
			if bool(out[i]["no_standing_room"]):
				continue
			var pv2: Vector3 = pts[i]
			var refp: Vector3 = snapped[main_ref]
			var alt := _stand_point_on_network(map, pv2, refp)
			if not bool(alt["found"]):
				continue
			rerouted[i] = offsets[i]
			snapped[i] = alt["point"]
			offsets[i] = float(alt["offset"])
			moved = true
	if moved:
		out = _census(map, names, pts, snapped, offsets, no_room, rerouted)
	for i in pts.size():
		var raw: Vector3 = pts[i]
		_resolved[_key(raw)] = {"point": snapped[i], "offset": float(offsets[i]),
								"found": not bool(no_room[i])}
	return out


func _main_reference(census: Array) -> int:
	## Index of an anchor on the largest cluster; -1 if there is no majority.
	for i in census.size():
		if int(census[i]["cluster_size"]) == int(census[i]["main_cluster_size"]):
			return i
	return -1


func _stand_point_on_network(map: RID, p: Vector3, ref: Vector3) -> Dictionary:
	## Nearest standing room on p's storey that can walk to `ref` and back.
	## Mutual on purpose: a one-way drop is not somewhere a player arrives from.
	var r := 0.0
	while r <= STAND_SEARCH_M:
		var dirs := 1 if r == 0.0 else maxi(STAND_DIRS,
			int(ceil(TAU * r / STAND_STEP_M)))
		var best := Vector3.ZERO
		var best_d := INF
		for k in dirs:
			var a := TAU * float(k) / float(dirs)
			var q := p if r == 0.0 else p + Vector3(cos(a) * r, 0.0, sin(a) * r)
			var c = _stand_at(map, q, p.y)
			if c == null:
				continue
			var cv: Vector3 = c
			var d := cv.distance_to(p)
			if d >= best_d:
				continue
			if _reaches(map, cv, ref, true) and _reaches(map, ref, cv, true):
				best_d = d
				best = cv
		if best_d < INF:
			return {"point": best, "offset": best_d, "found": true}
		r += STAND_STEP_M
	return {"point": p, "offset": 0.0, "found": false}


func _census(map: RID, names: Array, pts: Array, snapped: Array,
			 offsets: Array, no_room: Array, rerouted: Array) -> Array:
	# Reachability, and the CLUSTERS it forms. Counting "reaches 0" was not
	# enough: Lot emits four duplicate anchor pairs per site (two markers 0.2 m
	# apart snap to one point), so a stranded anchor still reached its own twin
	# and passed. Sixteen of twenty-one anchors were off the main network and
	# the count said zero were stranded. What matters is whether an anchor is on
	# the LARGEST cluster, not whether it can see anybody at all.
	var n := pts.size()
	var parent := PackedInt32Array()
	parent.resize(n)
	for i in n:
		parent[i] = i
	var reach_count := PackedInt32Array()
	reach_count.resize(n)
	var can := []
	for i in n:
		var row := []
		for j in n:
			row.append(false if i == j
				else _reaches(map, snapped[i], snapped[j], true))
		can.append(row)
	for i in n:
		var c := 0
		for j in n:
			if bool(can[i][j]):
				c += 1
		reach_count[i] = c
	# Union on MUTUAL reachability only. Reachability is not symmetric here and
	# the asymmetry is the tolerance's, not the navmesh's: arrival is judged
	# within SNAP_MAX of the destination, so a route from the main network to an
	# anchor on a nearby island "arrives" while the route back off that island
	# stops nowhere near the main network. One directed edge was enough to union,
	# so an anchor reporting `reaches 0/16` still came out `cluster 16/16` -- the
	# census contradicting itself in two adjacent columns of the same row.
	for i in n:
		for j in range(i + 1, n):
			if not (bool(can[i][j]) and bool(can[j][i])):
				continue
			var ra := _find(parent, i)
			var rb := _find(parent, j)
			if ra != rb:
				parent[ra] = rb

	var size_of := {}
	for i in n:
		var r := _find(parent, i)
		size_of[r] = int(size_of.get(r, 0)) + 1
	var main_size := 0
	for k in size_of.keys():
		main_size = maxi(main_size, int(size_of[k]))

	var out: Array = []
	_stranded_names = {}
	for i in n:
		var s: Vector3 = snapped[i]
		var raw: Vector3 = pts[i]
		var csize: int = int(size_of[_find(parent, i)])
		# Two anchors on the same point is Lot emitting the same position twice.
		# Lot 0.28.0 merges them at source, so this should now find nothing --
		# which is the reason to keep it. It is how the duplicate was found.
		var twin := ""
		for j in n:
			if j != i and snapped[j].distance_to(s) <= 0.05:
				twin = names[j]
				break
		if csize < main_size:
			_stranded_names[names[i]] = true
		out.append({
			"name": names[i],
			"raw": [snappedf(raw.x, 0.1), snappedf(raw.y, 0.1), snappedf(raw.z, 0.1)],
			"snap": [snappedf(s.x, 0.1), snappedf(s.y, 0.1), snappedf(s.z, 0.1)],
			"snap_m": snappedf(float(offsets[i]), 0.01),
			# The anchor's own storey had no walkable surface within reach. This
			# is a room that did not bake, and it is a different fact from an
			# anchor that stands somewhere real but cannot be walked to.
			"no_standing_room": bool(no_room[i]),
			# > 0 means the nearest standing room was on a component no route
			# reaches, and this is the nearest CONNECTED one instead. The value
			# is how far the nearest one was, so both readings survive.
			"unreachable_stand_m": snappedf(float(rerouted[i]), 0.01),
			"reaches": reach_count[i],
			"of": n - 1,
			"cluster_size": csize,
			"main_cluster_size": main_size,
			"coincident_with": twin,
		})
	return out


func _find(parent: PackedInt32Array, i: int) -> int:
	var r := i
	while parent[r] != r:
		r = parent[r]
	while parent[i] != r:
		var nxt := parent[i]
		parent[i] = r
		i = nxt
	return r


func _stranded_blame(leg_label: String) -> String:
	## The endpoint of this leg that reaches nothing, if either does. The label
	## is "a->b"; either end being isolated makes the leg say more about the
	## anchor than about the route between them.
	var parts := leg_label.split("->")
	for part in parts:
		if _stranded_names.has(part):
			return part
	return ""


func _prove_path(map: RID, label: String, a: Vector3, b: Vector3) -> Dictionary:
	var ia := _stand_point(map, a)
	var ib := _stand_point(map, b)
	var sa: Vector3 = ia["point"]
	var sb: Vector3 = ib["point"]
	var da: float = ia["offset"]
	var db: float = ib["offset"]
	if not ia["found"] or not ib["found"]:
		# Not "off the navmesh by a bit" -- no walkable surface anywhere on this
		# anchor's own storey within %.0f m. That is a room that did not bake.
		return {"leg": label, "ok": false, "no_standing_room": true,
				"detail": "no standing room on the anchor's own storey within %.0f m (from %s)"
				% [STAND_SEARCH_M,
				   "start" if not ia["found"] else "target"]}
	# How far a body has to stand from the marker is intel, not a verdict. A
	# loot marker in the middle of an 8 x 6 m vault block is 3 m from the
	# nearest floor and the level is fine; the old SNAP_MAX proximity test
	# called that an off-mesh anchor. Report the distance, judge the route.
	var far := maxf(da, db)
	var path := NavigationServer3D.map_get_path(map, sa, sb, true)
	if path.size() < 2:
		return {"leg": label, "ok": false, "detail": "no navmesh path"}
	var endgap := path[path.size() - 1].distance_to(sb)
	if endgap > SNAP_MAX:
		var pe := path[path.size() - 1]
		var h_gap := Vector2(pe.x - sb.x, pe.z - sb.z).length()
		var v_gap := absf(pe.y - sb.y)
		if h_gap <= SNAP_MAX * 1.5 and v_gap > 1.0:
			# walkable route reaches directly below/above the anchor; the
			# remaining gap is pure vertical = ladder/drop access. That
			# traversal is game code (climb volumes), gated by Deli
			# Counter's ladder checks -- report as intel, don't fail.
			return {"leg": label, "ok": true, "vertical_access": true,
					"stand_offset_m": snappedf(far, 0.01),
					"detail": "walkable to (%.1f, %.1f, %.1f); %.1f m VERTICAL access (ladder/drop) to anchor at (%.1f, %.1f, %.1f)"
					% [pe.x, pe.y, pe.z, v_gap, sb.x, sb.y, sb.z]}
		return {"leg": label, "ok": false,
				"stand_offset_m": snappedf(far, 0.01),
				"detail": "path stops %.2f m short (disjoint islands): ends (%.1f, %.1f, %.1f), target stands at (%.1f, %.1f, %.1f), raw target (%.1f, %.1f, %.1f)"
				% [endgap, pe.x, pe.y, pe.z, sb.x, sb.y, sb.z, b.x, b.y, b.z]}
	var length := 0.0
	for i in range(path.size() - 1):
		length += path[i].distance_to(path[i + 1])
	var rep := {"leg": label, "ok": true, "length_m": length,
			"stand_offset_m": snappedf(far, 0.01),
			"detail": "path %.1f m, %d points" % [length, path.size()]}
	if far > SNAP_MAX:
		# The route is fine; the marker is buried. Worth saying -- a marker a
		# body cannot get within SNAP_MAX of is a marker inside the furniture.
		rep["detail"] += "; nearest standing room is %.1f m from the marker" % far
		rep["marker_buried"] = true
	return rep


func _spawn_walker(walker_name: String, at: Vector3, targets: Array) -> void:
	# snap the spawn onto the navmesh: a marker hanging off-mesh must be a
	# reported finding, not a walker free-falling out of the world
	var map: RID = get_world_3d().navigation_map
	var snapped_pos := NavigationServer3D.map_get_closest_point(map, at)
	var off := at.distance_to(snapped_pos)
	if off > 5.0:
		_walkers.append({"name": walker_name, "body": null, "agent": null,
						 "targets": targets, "ti": 0, "reached": 0,
						 "travelled": 0.0, "last_pos": at, "stall": 0.0,
						 "finished": true,
						 "status": "spawn_off_mesh(%.1fm)" % off})
		return
	at = snapped_pos + Vector3(0, 0.5, 0)
	var body := CharacterBody3D.new()
	body.name = "NavQA_" + walker_name
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = AGENT_RADIUS * 0.7
	capsule.height = AGENT_HEIGHT
	shape.shape = capsule
	body.add_child(shape)
	# walkers collide with the WORLD only, never each other -- four capsules
	# spawned in a line grid-lock instantly otherwise
	body.collision_layer = 0
	body.collision_mask = 1
	# floor slope must match the BAKE's agent_max_slope (agent contract):
	# tall-story basement ramps run past the 45 deg default and the engine
	# then treats the ramp as a WALL -- every walker jams at the stair mouth
	# (warehouse_district: 4.2-4.5 m stories, ramp ~49-52 deg)
	body.floor_max_angle = deg_to_rad(_envf("DC_NAV_SLOPE", 55.0) + 1.0)
	# Stay glued to a descending slope instead of launching off its crest and
	# spending the next frames airborne, where the step probe cannot fire.
	body.floor_snap_length = STEP_UP
	add_child(body)
	body.global_position = at
	if targets.is_empty():
		targets = [at]
	var w := {"name": walker_name, "body": body,
			  "targets": targets, "ti": 0, "reached": 0,
			  "travelled": 0.0, "last_pos": at, "stall": 0.0,
			  "finished": false, "status": "running",
			  "path": PackedVector3Array(), "pi": 0}
	_set_leg(w, targets[0])
	_walkers.append(w)


func _set_leg(w: Dictionary, target: Vector3) -> void:
	## precompute the waypoint path with the same API the proofs use --
	## NavigationAgent3D does not produce paths in this headless context.
	## A VERTICAL-access leg (ladder/drop -- the proofs' own classification)
	## is traversed by game code, not walking: credit it and advance.
	var map: RID = get_world_3d().navigation_map
	var body: CharacterBody3D = w["body"]
	# Same question the proofs ask, so a walker is never sent somewhere the
	# proofs would not have counted: map_get_closest_point is omnidirectional and
	# would aim this leg at the counter top above the target rather than the
	# floor beside it, then report the walker STUCK for failing to climb it.
	var sa := _snap(map, body.global_position)
	var sb := _snap(map, target)
	var path := NavigationServer3D.map_get_path(map, sa, sb, true)
	if path.size() >= 2:
		var pe := path[path.size() - 1]
		var h_gap := Vector2(pe.x - sb.x, pe.z - sb.z).length()
		var v_gap := absf(pe.y - sb.y)
		if pe.distance_to(sb) > SNAP_MAX and h_gap <= SNAP_MAX * 1.5 \
				and v_gap > 1.0:
			w["reached"] += 1
			w["ti"] += 1
			w["vertical_legs"] = int(w.get("vertical_legs", 0)) + 1
			if w["ti"] >= (w["targets"] as Array).size():
				w["finished"] = true
				w["status"] = "ok(%d vertical leg(s) via ladder)" % w["vertical_legs"]
			else:
				_set_leg(w, w["targets"][w["ti"]])
			return
	w["path"] = path
	w["pi"] = 0
	w["wp_best"] = INF


func _blocked_by(body: CharacterBody3D) -> Array:
	## Every surface the capsule is in contact with after this frame's
	## move_and_slide, named. Valid only in the same frame as that call.
	var out: Array = []
	for i in body.get_slide_collision_count():
		var c := body.get_slide_collision(i)
		var o = c.get_collider()
		var nm := "<freed>"
		var np := ""
		if o is Node:
			nm = String((o as Node).name)
			np = String((o as Node).get_path())
		var n := c.get_normal()
		var p := c.get_position()
		out.append({
			"collider": nm,
			"path": np,
			"normal": [snappedf(n.x, 0.01), snappedf(n.y, 0.01), snappedf(n.z, 0.01)],
			"at": [snappedf(p.x, 0.1), snappedf(p.y, 0.1), snappedf(p.z, 0.1)],
		})
	return out


static func _passed(pos: Vector3, wp: Vector3, nxt: Vector3) -> bool:
	## Has the body gone PAST this waypoint on its way to the next one?
	##
	## Proximity cannot answer this. A corner waypoint 0.45 m away is near while
	## the body is still on the wrong side of the corner, so a radius test marks
	## it reached and the body steers at whatever comes after it -- on
	## warehouse_district, through the wall the corner existed to avoid. This
	## asks the direction question instead: project the body onto the leg
	## leaving the waypoint, and call it consumed only once it is on the far
	## side. Horizontal only, for the same reason the proximity test is: the
	## capsule centre rides about half its height above the nav surface, and a
	## 3D test folds that constant offset into every comparison.
	var leg := Vector2(nxt.x - wp.x, nxt.z - wp.z)
	if leg.length() < 0.01:
		return true
	var rel := Vector2(pos.x - wp.x, pos.z - wp.z)
	return rel.dot(leg.normalized()) > 0.0


func _drive(w: Dictionary, delta: float) -> void:
	var body: CharacterBody3D = w["body"]
	var target: Vector3 = w["targets"][w["ti"]]

	var h_arrive := Vector2(body.global_position.x - target.x,
							body.global_position.z - target.z).length()
	var path_now: PackedVector3Array = w["path"]
	var at_path_end: bool = w["pi"] >= path_now.size() and (path_now.size() == 0
		or body.global_position.distance_to(path_now[path_now.size() - 1]) < 1.0)
	if h_arrive < ARRIVE_DIST or at_path_end:
		w["reached"] += 1
		w["ti"] += 1
		w["repaths"] = 0
		if w["ti"] >= w["targets"].size():
			w["finished"] = true
			var vl := int(w.get("vertical_legs", 0))
			w["status"] = "ok" if vl == 0 else "ok(%d vertical leg(s) via ladder)" % vl
			return
		_set_leg(w, w["targets"][w["ti"]])
		return

	# follow the precomputed waypoints. Consume by HORIZONTAL distance -- the
	# capsule center rides ~0.9 m above the nav surface, so 3D radii mix the
	# constant vertical offset into the test. A waypoint pinned overhead or
	# underfoot (hd ~ 0, big vd -- fell beside a stair flight) is skipped:
	# steering can never resolve it and freezes the walker otherwise.
	var path: PackedVector3Array = w["path"]
	var pi: int = w["pi"]
	while pi < path.size():
		var wp: Vector3 = path[pi]
		var hd := Vector2(body.global_position.x - wp.x,
						  body.global_position.z - wp.z).length()
		var vd := absf(body.global_position.y - wp.y)
		if hd < WP_RADIUS and (vd < 1.6 or hd < 0.1):
			pi += 1
		elif pi + 1 < path.size() and _passed(body.global_position, wp,
				path[pi + 1]):
			# Not near, but behind: the body has rounded this waypoint and is
			# on its way to the next. Distance alone cannot tell those apart,
			# which is the whole defect this replaces.
			pi += 1
		else:
			break
	if pi != int(w["pi"]):
		w["wp_best"] = INF     # fresh waypoint, fresh progress baseline
	w["pi"] = pi
	var next: Vector3 = path[pi] if pi < path.size() else target
	var to_next := next - body.global_position
	var vel: Vector3
	if to_next.y > 0.1:
		# CLIMBING segment (stair flight): follow the nav path in 3D instead
		# of fighting gravity into every riser with a flat velocity. The
		# capsule still collides -- blocking geometry still stops it.
		vel = to_next.normalized() * WALK_SPEED if to_next.length() > 0.05 \
			else Vector3.ZERO
	else:
		var dir := Vector3(to_next.x, 0.0, to_next.z)
		vel = dir.normalized() * WALK_SPEED if dir.length() > 0.05 \
			else Vector3.ZERO
		# Gravity only while AIRBORNE. Accumulating it every frame on a body
		# that is already standing pins the capsule into the junction where a
		# ramp meets the floor and fights the slide that would carry it up. A
		# waypoint on a stair flight often sits at the same height as the body,
		# so the climbing branch above never fires and this one has to be able
		# to walk a slope.
		vel.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * delta
	body.velocity = vel
	body.move_and_slide()

	# kinematic step-up (the game rig's max_step_up, from the agent contract):
	# on wall contact while driving, probe up-then-forward and take the step.
	# Triggers on CONTACT like the old hop did (a sliding capsule never drops
	# below a %-speed threshold), but probes instead of leaping, so it cannot
	# wedge under a stair flight.
	if body.is_on_floor() and body.is_on_wall() \
			and Vector2(vel.x, vel.z).length() > 0.1:
		# One 0.5 m probe assumed the only thing that can stop a body at a stair
		# mouth is the riser in front of it. walkup_siege proved otherwise: a
		# 39.2 deg ramp -- legal by every number in agent_contract.json, and
		# carrying an eighteen-point navmesh path -- jammed four bots because
		# the lift had nowhere to go. Try smaller lifts before giving up.
		#
		# And record WHICH probe failed. "No headroom to lift" is a finding
		# about the stairwell, against clearances.min_headroom_m; "no room
		# ahead" is a finding about the obstacle. A walker that gives up without
		# saying which sends the reader to the wrong repo.
		var fwd := Vector3(vel.x, 0.0, vel.z).normalized()
		var stepped := false
		var lifts_blocked := 0
		var lifts := [STEP_UP, STEP_UP * 0.7, STEP_UP * 0.4]
		for lift in lifts:
			var up := Vector3(0.0, float(lift), 0.0)
			if body.test_move(body.global_transform, up):
				lifts_blocked += 1
				continue
			var lifted := body.global_transform.translated(up)
			if body.test_move(lifted, fwd * STEP_FWD):
				continue
			body.global_position += up + fwd * STEP_FWD
			body.velocity.y = 0.0
			stepped = true
			break
		if stepped:
			w.erase("step_fail")
		else:
			w["step_fail"] = ("nothing overhead to lift into (%d/%d probes blocked)"
							  % [lifts_blocked, lifts.size()]) \
				if lifts_blocked == lifts.size() \
				else "lifted clear but nothing to step onto ahead"

	var moved := body.global_position.distance_to(w["last_pos"])
	w["travelled"] += moved
	w["last_pos"] = body.global_position

	# stall = no PROGRESS toward the next waypoint. Raw movement lies: a
	# capsule wall-sliding or step-hopping in place registers plenty of
	# motion while going nowhere, and never triggers a repath.
	var d_next := body.global_position.distance_to(next)
	var best: float = w.get("wp_best", INF)
	if d_next < best - 0.05:
		w["wp_best"] = d_next
		w["stall"] = 0.0
	else:
		w["stall"] += delta
		if w["stall"] > STUCK_SECS:
			var pp := body.global_position
			var rp := int(w.get("repaths", 0))
			if rp < MAX_REPATHS:
				# Jammed or steering-frozen (a fall beside a stair leaves the
				# next waypoint directly overhead; horizontal steering then
				# zeroes out). Do what a real nav agent does: re-path from
				# HERE and keep going.
				w["repaths"] = rp + 1
				w["stall"] = 0.0
				# reseat the capsule onto the navmesh first: a body wedged in
				# geometry cannot escape by pathing alone. Bounded by SNAP_MAX
				# so it can never fake real traversal -- the proofs own that.
				var seat := NavigationServer3D.map_get_closest_point(
					get_world_3d().navigation_map, pp)
				if pp.distance_to(seat) <= SNAP_MAX:
					body.global_position = seat + Vector3(0, 0.4, 0)
					body.velocity = Vector3.ZERO
				print("[nav-qa] walker %s repath %d/%d at (%.1f, %.1f, %.1f) -> target_%d"
					% [w["name"], rp + 1, MAX_REPATHS, pp.x, pp.y, pp.z, w["ti"]])
				_set_leg(w, w["targets"][w["ti"]])
			else:
				w["finished"] = true
				w["status"] = "stuck@target_%d at (%.1f, %.1f, %.1f)" \
					% [w["ti"], pp.x, pp.y, pp.z]
				# `at` is set for a walker that ran out the clock but was not
				# set for one that gave up, so the position existed only inside
				# the status prose and nothing could read it as a number.
				w["at"] = [snappedf(pp.x, 0.1), snappedf(pp.y, 0.1),
						   snappedf(pp.z, 0.1)]
				# WHAT it is stuck against. A coordinate alone sends the reader
				# to a plan view to guess, and guessing does not work: seed 5017
				# put all four walkers on the same point with six metres of open
				# floor around it and a clear line to the target, and an offline
				# reconstruction of the colliders could not see the obstacle --
				# because the obstacle is whatever move_and_slide is touching,
				# and only the engine knows that. An empty list is an answer
				# too, and a different one: touching nothing means the steering
				# froze rather than the geometry blocked.
				var against := _blocked_by(body)
				w["blocked_by"] = against
				w["waypoint"] = [snappedf(next.x, 0.1), snappedf(next.y, 0.1),
								 snappedf(next.z, 0.1)]
				w["waypoint_dist_m"] = snappedf(d_next, 0.01)
				w["path_index"] = pi
				w["path_points"] = path.size()
				w["on_floor"] = body.is_on_floor()
				w["on_wall"] = body.is_on_wall()
				var names := []
				for c in against:
					names.append(str(c.get("collider", "?")))
				print("[nav-qa] walker %s STUCK at (%.1f, %.1f, %.1f) %.2f m from waypoint %d/%d (%.1f, %.1f, %.1f); on_floor=%s on_wall=%s; touching: %s"
					% [w["name"], pp.x, pp.y, pp.z, d_next, pi, path.size(),
					   next.x, next.y, next.z, body.is_on_floor(),
					   body.is_on_wall(),
					   ", ".join(names) if names.size() > 0
					   else "NOTHING -- the steering froze, the geometry did not block"])
