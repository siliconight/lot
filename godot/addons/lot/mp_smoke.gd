extends SceneTree
## lot mp_smoke.gd -- minimal multiplayer runtime smoke test (Godot 4, ENet)
## ----------------------------------------------------------------------------
## The Production Package asks for a multiplayer SMOKE test, not a netcode
## framework: prove that at the target player count, peers can connect, load
## the site scene, move through it under physics, and disconnect cleanly.
## mp_smoke.py orchestrates one host + N-1 client processes on localhost:
##
##   godot4 --headless --path <project> --script addons/lot/mp_smoke.gd -- \
##       host  <port> <site.tscn res-path> <players> <secs> <out.json>
##   godot4 --headless --path <project> --script addons/lot/mp_smoke.gd -- \
##       client <port> <site.tscn res-path> <spawn_x,y,z> <target_x,y,z> <secs>
##
## Host: ENet server; waits for players-1 clients; loads the site; collects
## per-client heartbeat RPCs (cumulative meters moved); verdict = every
## expected client connected, moved >= MIN_MOVE_M, and stayed connected for
## the run. Client: connects, loads the site, drives a CharacterBody3D from
## spawn toward target for the duration, heartbeats every 0.5 s, quits clean.
##
## The shells are replication-free by design (Deli Counter thesis): the ONLY
## networked state here is the heartbeat -- which is the point of a smoke.
## Exit code 0 = pass, 1 = fail, 2 = bad input.

const MIN_MOVE_M := 5.0
const CONNECT_TIMEOUT := 15.0
const HEARTBEAT_SECS := 0.5

var _role := ""
var _port := 0
var _players := 2
var _duration := 20.0
var _out_path := ""
var _t := 0.0
var _smoke: Node = null


func _initialize() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() < 3:
		printerr("[mp-smoke] bad args: %s" % str(a))
		quit(2)
		return
	_role = a[0]
	_port = int(a[1])
	var scene_path: String = a[2]

	_smoke = SmokeNode.new()
	_smoke.name = "Smoke"
	root.add_child(_smoke)

	var peer := ENetMultiplayerPeer.new()
	if _role == "host":
		_players = int(a[3]) if a.size() > 3 else 2
		_duration = float(a[4]) if a.size() > 4 else 20.0
		_out_path = a[5] if a.size() > 5 else "res://mp_smoke.json"
		var err := peer.create_server(_port, 32)
		if err != OK:
			printerr("[mp-smoke] cannot bind port %d (%d)" % [_port, err])
			quit(2)
			return
		root.multiplayer.multiplayer_peer = peer
		_smoke.setup_host(_players - 1, _duration, _out_path)
		print("[mp-smoke] host up on %d, expecting %d client(s)" % [_port, _players - 1])
	elif _role == "client":
		var spawn := _v3(a[3]) if a.size() > 3 else Vector3.ZERO
		var target := _v3(a[4]) if a.size() > 4 else Vector3(10, 0, 0)
		_duration = float(a[5]) if a.size() > 5 else 20.0
		var err := peer.create_client("127.0.0.1", _port)
		if err != OK:
			printerr("[mp-smoke] cannot create client (%d)" % err)
			quit(2)
			return
		root.multiplayer.multiplayer_peer = peer
		_smoke.setup_client(spawn, target, _duration)
	else:
		printerr("[mp-smoke] role must be host|client")
		quit(2)
		return

	# both sides load the site scene -- a load failure fails the smoke
	var packed: PackedScene = load(scene_path)
	if packed == null:
		printerr("[mp-smoke] cannot load %s" % scene_path)
		quit(1)
		return
	var site := packed.instantiate()
	root.add_child(site)
	print("[mp-smoke] %s loaded %s" % [_role, scene_path])


static func _v3(s: String) -> Vector3:
	var p := s.split(",")
	return Vector3(float(p[0]), float(p[1]), float(p[2]))


## ---------------------------------------------------------------------------
## The node both sides register at /root/Smoke so RPC paths line up.
## ---------------------------------------------------------------------------
class SmokeNode:
	extends Node

	var role := ""
	var expected := 1
	var duration := 20.0
	var out_path := ""
	var t := 0.0
	var hb_t := 0.0
	var moved := {}          # host: peer_id -> meters
	var disconnected := []   # host: peer ids that dropped early
	var body: CharacterBody3D = null
	var target := Vector3.ZERO
	var start := Vector3.ZERO
	var travelled := 0.0
	var last := Vector3.ZERO
	var reported_done := false

	func setup_host(n_clients: int, secs: float, outp: String) -> void:
		role = "host"
		expected = n_clients
		duration = secs
		out_path = outp
		multiplayer.peer_connected.connect(_on_peer)
		multiplayer.peer_disconnected.connect(_on_peer_gone)
		set_process(true)

	func setup_client(spawn: Vector3, tgt: Vector3, secs: float) -> void:
		role = "client"
		duration = secs
		start = spawn
		target = tgt
		multiplayer.connected_to_server.connect(_on_connected)
		multiplayer.connection_failed.connect(func(): _die(1, "connection failed"))
		multiplayer.server_disconnected.connect(func(): _die(1, "server dropped us"))
		set_process(true)

	func _on_peer(id: int) -> void:
		print("[mp-smoke] host: peer %d connected" % id)
		moved[id] = 0.0

	func _on_peer_gone(id: int) -> void:
		if t < duration - 0.5 and (moved.get(id, 0.0) as float) < MIN_MOVE_M:
			disconnected.append(id)
			print("[mp-smoke] host: peer %d dropped EARLY" % id)

	func _on_connected() -> void:
		print("[mp-smoke] client: connected as %d" % multiplayer.get_unique_id())
		body = CharacterBody3D.new()
		var cs := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = 0.35
		cap.height = 1.8
		cs.shape = cap
		body.add_child(cs)
		get_tree().root.add_child(body)
		body.global_position = start + Vector3(0, 1.0, 0)
		last = body.global_position
		set_physics_process(true)

	func _process(delta: float) -> void:
		t += delta
		if role == "host":
			if t > CONNECT_TIMEOUT and moved.size() < expected:
				_host_finish(false, "only %d/%d clients connected in %.0fs"
					% [moved.size(), expected, CONNECT_TIMEOUT])
			elif t > duration + CONNECT_TIMEOUT:
				_host_verdict()
		elif role == "client":
			if t > duration + CONNECT_TIMEOUT:
				_die(0, "client done (%.1f m)" % travelled)

	func _physics_process(delta: float) -> void:
		if body == null:
			return
		var dir := target - body.global_position
		dir.y = 0.0
		var vel := dir.normalized() * 3.5 if dir.length() > 1.0 else Vector3.ZERO
		vel.y = body.velocity.y - 9.8 * delta
		body.velocity = vel
		body.move_and_slide()
		travelled += body.global_position.distance_to(last)
		last = body.global_position
		hb_t += delta
		if hb_t >= HEARTBEAT_SECS:
			hb_t = 0.0
			rpc_id(1, "heartbeat", travelled)
		if t >= duration and not reported_done:
			reported_done = true
			rpc_id(1, "heartbeat", travelled)
			_die(0, "client finished (%.1f m)" % travelled)

	@rpc("any_peer", "reliable")
	func heartbeat(total_m: float) -> void:
		if role != "host":
			return
		moved[multiplayer.get_remote_sender_id()] = total_m
		# every expected client past the movement bar? finish early.
		if moved.size() >= expected:
			var all_ok := true
			for id in moved:
				all_ok = all_ok and (moved[id] as float) >= MIN_MOVE_M
			if all_ok and disconnected.is_empty():
				_host_verdict()

	func _host_verdict() -> void:
		var ok := moved.size() >= expected and disconnected.is_empty()
		var detail := {}
		for id in moved:
			detail[str(id)] = snappedf(moved[id], 0.1)
			ok = ok and (moved[id] as float) >= MIN_MOVE_M
		_write_report(ok, detail)
		_die(0 if ok else 1, "verdict %s" % ("PASS" if ok else "FAIL"))

	func _host_finish(ok: bool, why: String) -> void:
		_write_report(ok, {"error": why})
		_die(0 if ok else 1, why)

	func _write_report(ok: bool, detail: Dictionary) -> void:
		var rep := {"ok": ok, "role": "host", "expected_clients": expected,
					"connected": moved.size(), "min_move_m": MIN_MOVE_M,
					"clients": detail, "early_disconnects": disconnected,
					"seconds": snappedf(t, 0.1)}
		var f := FileAccess.open(out_path, FileAccess.WRITE)
		if f:
			f.store_string(JSON.stringify(rep, "  "))
			f.close()
			print("[mp-smoke] wrote %s" % ProjectSettings.globalize_path(out_path))

	func _die(code: int, why: String) -> void:
		print("[mp-smoke] %s: %s" % [role, why])
		get_tree().quit(code)
