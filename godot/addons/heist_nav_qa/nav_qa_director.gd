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

const AGENT_RADIUS := 0.5
const AGENT_HEIGHT := 1.8
const SNAP_MAX := 2.0            # m; anchor farther than this off-mesh = fail
const WALK_SPEED := 4.0          # m/s
const STUCK_SECS := 4.0          # no progress this long = stuck
const TIME_LIMIT := 120.0        # hard cap on the simulation (seconds)
const ARRIVE_DIST := 1.5

var _report := {}
var _walkers: Array = []
var _sim_time := 0.0
var _done := false


func _ready() -> void:
	if run_on_ready:
		start_qa_run()


func start_qa_run() -> void:
	# let the nav bake + server sync settle before querying
	await get_tree().physics_frame
	await get_tree().physics_frame
	_run()


func _run() -> void:
	var map: RID = get_world_3d().navigation_map
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

	# ---- pass 2: simulated walkers ----------------------------------------
	var spine: Array = [home]
	for p in proxies:
		spine.append(p)
	for i in maxi(simulated_players, 1):
		_spawn_walker("player_%d" % i, home + Vector3(i * 0.7, 0.5, 0.0),
					  spine.slice(1))
	for i in mini(bot_count, bot_spawns.size() * 4):
		var s: Vector3 = bot_spawns[i % maxi(bot_spawns.size(), 1)] \
			if not bot_spawns.is_empty() else home
		_spawn_walker("bot_%d" % i, s + Vector3(0, 0.5, 0),
					  [_nearest(proxies, s)])

	_report["_proof_failures"] = proof_fail
	set_physics_process(true)


func _physics_process(delta: float) -> void:
	if _done:
		return
	_sim_time += delta
	var all_done := true
	for w in _walkers:
		if not w["finished"]:
			_drive(w, delta)
			all_done = all_done and w["finished"]
	if all_done or _sim_time > TIME_LIMIT:
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
		_report["walkers"].append(rep)
		if w["status"] != "ok":
			walk_fail += 1
		print("[nav-qa] walker %s: %s (%d/%d targets, %.1f m)"
			% [w["name"], w["status"], w["reached"], w["targets"].size(),
			   w["travelled"]])
	var ok: bool = _report["_proof_failures"] == 0 and walk_fail == 0
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
		return {"leg": label, "ok": false,
				"detail": "path stops %.2f m short (disjoint islands)" % endgap}
	var length := 0.0
	for i in range(path.size() - 1):
		length += path[i].distance_to(path[i + 1])
	return {"leg": label, "ok": true,
			"detail": "path %.1f m, %d points" % [length, path.size()]}


func _spawn_walker(walker_name: String, at: Vector3, targets: Array) -> void:
	var body := CharacterBody3D.new()
	body.name = "NavQA_" + walker_name
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = AGENT_RADIUS * 0.7
	capsule.height = AGENT_HEIGHT
	shape.shape = capsule
	body.add_child(shape)
	var agent := NavigationAgent3D.new()
	agent.radius = AGENT_RADIUS
	agent.height = AGENT_HEIGHT
	agent.path_desired_distance = 0.6
	agent.target_desired_distance = ARRIVE_DIST
	body.add_child(agent)
	add_child(body)
	body.global_position = at
	if targets.is_empty():
		targets = [at]
	agent.target_position = targets[0]
	_walkers.append({"name": walker_name, "body": body, "agent": agent,
					 "targets": targets, "ti": 0, "reached": 0,
					 "travelled": 0.0, "last_pos": at, "stall": 0.0,
					 "finished": false, "status": "running"})


func _drive(w: Dictionary, delta: float) -> void:
	var body: CharacterBody3D = w["body"]
	var agent: NavigationAgent3D = w["agent"]
	var target: Vector3 = w["targets"][w["ti"]]

	if body.global_position.distance_to(target) < ARRIVE_DIST:
		w["reached"] += 1
		w["ti"] += 1
		if w["ti"] >= w["targets"].size():
			w["finished"] = true
			w["status"] = "ok"
			return
		agent.target_position = w["targets"][w["ti"]]
		return

	var next := agent.get_next_path_position()
	var dir := (next - body.global_position)
	dir.y = 0.0
	var vel := dir.normalized() * WALK_SPEED if dir.length() > 0.05 else Vector3.ZERO
	vel.y = body.velocity.y - 9.8 * delta
	body.velocity = vel
	body.move_and_slide()

	var moved := body.global_position.distance_to(w["last_pos"])
	w["travelled"] += moved
	w["last_pos"] = body.global_position
	if moved < 0.01 * (WALK_SPEED * delta) + 0.001:
		w["stall"] += delta
		if w["stall"] > STUCK_SECS:
			w["finished"] = true
			w["status"] = "stuck@target_%d" % w["ti"]
	else:
		w["stall"] = 0.0
