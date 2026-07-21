extends Node
## mp_smoke_node.gd -- the networked half of the multiplayer smoke test.
## Registered at /root/Smoke on BOTH sides so @rpc paths line up (RPC methods
## live in a real script file, not an inner class -- Godot resolves rpc
## configs per script resource). See mp_smoke.gd for the launcher/orchestra.

const MIN_MOVE_M := 5.0
# generous: clients cold-load the site scene AFTER connecting starts being
# possible, staggered 3s apart -- 15s raced the last client's load and lost
const CONNECT_TIMEOUT := 45.0
const HEARTBEAT_SECS := 0.5

var role := ""
var expected := 1
var duration := 20.0
var out_path := ""
var t := 0.0
var hb_t := 0.0
var moved := {}          # host: peer_id -> meters
var disconnected: Array = []
var body: CharacterBody3D = null
var target := Vector3.ZERO
var start := Vector3.ZERO
var travelled := 0.0
var last := Vector3.ZERO
var reported_done := false
var finished := false


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
	multiplayer.connection_failed.connect(_on_conn_failed)
	multiplayer.server_disconnected.connect(_on_server_gone)
	set_process(true)


func _on_conn_failed() -> void:
	_die(1, "connection failed")


func _on_server_gone() -> void:
	# The host quits the moment every client has moved >= MIN_MOVE_M -- an
	# early PASS teardown, not a failure. A client that already did its part
	# (finished its run OR crossed the movement bar) treats the disconnect
	# as the expected end of the test.
	if reported_done or travelled >= MIN_MOVE_M:
		_die(0, "server closed after we did our part (%.1f m)" % travelled)
	else:
		_die(1, "server dropped us mid-run at %.1f m" % travelled)


func _on_peer(id: int) -> void:
	print("[mp-smoke] host: peer %d connected" % id)
	moved[id] = 0.0


func _on_peer_gone(id: int) -> void:
	var m: float = moved.get(id, 0.0)
	if m < MIN_MOVE_M:
		disconnected.append(id)
		print("[mp-smoke] host: peer %d dropped EARLY (%.1f m)" % [id, m])


func _on_connected() -> void:
	print("[mp-smoke] client: connected as %d" % multiplayer.get_unique_id())
	body = CharacterBody3D.new()
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.35
	cap.height = 1.8
	cs.shape = cap
	body.add_child(cs)
	var slope := OS.get_environment("DC_NAV_SLOPE")
	body.floor_max_angle = deg_to_rad((float(slope) if slope != "" else 55.0) + 1.0)
	get_tree().root.add_child(body)
	body.global_position = start + Vector3(0, 1.0, 0)
	last = body.global_position
	set_physics_process(true)


var _telemetry := false
var _tel_t := 0.0


func start_status_telemetry() -> void:
	_telemetry = true


func _process(delta: float) -> void:
	if finished:
		return
	t += delta
	if role == "host":
		if t > CONNECT_TIMEOUT and moved.size() < expected:
			_host_finish(false, "only %d/%d clients connected in %.0fs"
				% [moved.size(), expected, CONNECT_TIMEOUT])
		elif t > duration + CONNECT_TIMEOUT:
			_host_verdict()
	elif role == "client":
		if _telemetry:
			_tel_t += delta
			if _tel_t >= 2.0:
				_tel_t = 0.0
				var mp := multiplayer.multiplayer_peer
				if mp != null and body == null:
					print("[mp-smoke] client status: %d (0=disc 1=connecting 2=connected)"
						% mp.get_connection_status())
		if t > duration + CONNECT_TIMEOUT:
			_die(0, "client done (%.1f m)" % travelled)


var _stall_t := 0.0
var _detour_t := 0.0
var _detour_sign := 1.0


func _physics_process(delta: float) -> void:
	if body == null or finished:
		return
	var dir := target - body.global_position
	dir.y = 0.0
	# STALL DETOUR: this walker has NO pathing (the smoke bar is "moved
	# >= 5 m through real collision", not navigation) -- a straight beeline
	# into a wall must not false-fail a good site (storage_row: client0
	# walked 2.6 m into a corner and ground there for its whole run, while
	# the pathing walktest PASSED the same site). When progress stalls,
	# steer ~60 deg off-line for a beat, alternating sides.
	if _detour_t > 0.0:
		_detour_t -= delta
		dir = dir.rotated(Vector3.UP, _detour_sign * 1.05)
	var vel := Vector3.ZERO
	if dir.length() > 1.0:
		vel = dir.normalized() * 3.5
	vel.y = body.velocity.y - 9.8 * delta
	body.velocity = vel
	body.move_and_slide()
	var step := body.global_position.distance_to(last)
	if step < 0.02 and vel.length() > 1.0:
		_stall_t += delta
		if _stall_t > 1.5:
			_stall_t = 0.0
			_detour_t = 1.5
			_detour_sign = -_detour_sign
	else:
		_stall_t = maxf(0.0, _stall_t - delta)
	travelled += step
	last = body.global_position
	hb_t += delta
	if hb_t >= HEARTBEAT_SECS:
		hb_t = 0.0
		heartbeat.rpc_id(1, travelled)
	if t >= duration and not reported_done:
		reported_done = true
		heartbeat.rpc_id(1, travelled)
		_die(0, "client finished (%.1f m)" % travelled)


@rpc("any_peer", "reliable")
func heartbeat(total_m: float) -> void:
	if role != "host":
		return
	moved[multiplayer.get_remote_sender_id()] = total_m
	if moved.size() >= expected:
		var all_ok := true
		for id in moved:
			var m: float = moved[id]
			all_ok = all_ok and m >= MIN_MOVE_M
		if all_ok and disconnected.is_empty():
			_host_verdict()


func _host_verdict() -> void:
	var ok := moved.size() >= expected and disconnected.is_empty()
	var detail := {}
	for id in moved:
		var m: float = moved[id]
		detail[str(id)] = snappedf(m, 0.1)
		ok = ok and m >= MIN_MOVE_M
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
	finished = true
	print("[mp-smoke] %s: %s" % [role, why])
	get_tree().quit(code)
