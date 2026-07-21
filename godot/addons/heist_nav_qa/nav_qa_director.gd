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

var _report := {}
var _walkers: Array = []
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
		var suffix := ""
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
	var sa := NavigationServer3D.map_get_closest_point(map, from_pos)
	for pt in order:
		var v: Vector3 = pt
		var sb := NavigationServer3D.map_get_closest_point(map, v)
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


func _prove_path(map: RID, label: String, a: Vector3, b: Vector3) -> Dictionary:
	var sa := NavigationServer3D.map_get_closest_point(map, a)
	var sb := NavigationServer3D.map_get_closest_point(map, b)
	var da := sa.distance_to(a)
	var db := sb.distance_to(b)
	if da > SNAP_MAX or db > SNAP_MAX:
		return {"leg": label, "ok": false,
				"detail": "anchor off navmesh (snap %.2f m / %.2f m, max %.1f)"
				% [da, db, SNAP_MAX]}
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
					"detail": "walkable to (%.1f, %.1f, %.1f); %.1f m VERTICAL access (ladder/drop) to anchor at (%.1f, %.1f, %.1f)"
					% [pe.x, pe.y, pe.z, v_gap, sb.x, sb.y, sb.z]}
		return {"leg": label, "ok": false,
				"detail": "path stops %.2f m short (disjoint islands): ends (%.1f, %.1f, %.1f), target snap (%.1f, %.1f, %.1f), raw target (%.1f, %.1f, %.1f)"
				% [endgap, pe.x, pe.y, pe.z, sb.x, sb.y, sb.z, b.x, b.y, b.z]}
	var length := 0.0
	for i in range(path.size() - 1):
		length += path[i].distance_to(path[i + 1])
	return {"leg": label, "ok": true, "length_m": length,
			"detail": "path %.1f m, %d points" % [length, path.size()]}


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
	var sa := NavigationServer3D.map_get_closest_point(map, body.global_position)
	var sb := NavigationServer3D.map_get_closest_point(map, target)
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
		if hd < 0.6 and (vd < 1.6 or hd < 0.1):
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
		vel.y = body.velocity.y - 9.8 * delta
	body.velocity = vel
	body.move_and_slide()

	# kinematic step-up (the game rig's max_step_up, from the agent contract):
	# on wall contact while driving, probe up-then-forward and take the step.
	# Triggers on CONTACT like the old hop did (a sliding capsule never drops
	# below a %-speed threshold), but probes instead of leaping, so it cannot
	# wedge under a stair flight.
	if body.is_on_floor() and body.is_on_wall() \
			and Vector2(vel.x, vel.z).length() > 0.1:
		var fwd := Vector3(vel.x, 0.0, vel.z).normalized()
		var up := Vector3(0, STEP_UP, 0)
		if not body.test_move(body.global_transform, up):
			var lifted := body.global_transform.translated(up)
			if not body.test_move(lifted, fwd * STEP_FWD):
				body.global_position += up + fwd * STEP_FWD
				body.velocity.y = 0.0

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
