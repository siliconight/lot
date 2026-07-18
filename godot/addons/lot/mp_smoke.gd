extends SceneTree
## lot mp_smoke.gd -- minimal multiplayer runtime smoke test (Godot 4, ENet)
## ----------------------------------------------------------------------------
## The Production Package asks for a multiplayer SMOKE test, not a netcode
## framework: prove that at the target player count, peers can connect, load
## the site scene, move through it under physics, and disconnect cleanly.
## mp_smoke.py orchestrates one host + N-1 client processes on localhost:
##
##   godot4 --headless --path <project> --script addons/lot/mp_smoke.gd -- \
##       host  <port> <site.tscn res-path> <players> <secs> <out res-path>
##   godot4 --headless --path <project> --script addons/lot/mp_smoke.gd -- \
##       client <port> <site.tscn res-path> <spawn_x,y,z> <target_x,y,z> <secs>
##
## The networked node (RPCs, movement, verdict) lives in mp_smoke_node.gd,
## registered at /root/Smoke on both sides so rpc paths line up. The shells
## are replication-free by design (Deli Counter thesis): the only networked
## state here is the heartbeat -- which is the point of a smoke.
## Exit code 0 = pass, 1 = fail, 2 = bad input.

const SMOKE_NODE := "res://addons/lot/mp_smoke_node.gd"

var _args: PackedStringArray = []
var _pending := true


func _initialize() -> void:
	# 4.7 --script mode: during _initialize the root is not inside the tree
	# yet (root.multiplayer is null, added nodes read identity transforms).
	# Parse args only; ALL setup waits for the first process frame.
	_args = OS.get_cmdline_user_args()
	if _args.size() < 3:
		printerr("[mp-smoke] bad args: %s" % str(_args))
		quit(2)


func _process(_delta: float) -> bool:
	if _pending:
		_pending = false
		_setup()
	return false


func _setup() -> void:
	var a := _args
	var role: String = a[0]
	var port := int(a[1])
	var scene_path: String = a[2]

	var smoke_script: Script = load(SMOKE_NODE)
	if smoke_script == null:
		printerr("[mp-smoke] cannot load %s" % SMOKE_NODE)
		quit(2)
		return
	var smoke: Node = smoke_script.new()
	smoke.name = "Smoke"
	root.add_child(smoke)

	var peer := ENetMultiplayerPeer.new()
	if role == "host":
		var players := int(a[3]) if a.size() > 3 else 2
		var secs := float(a[4]) if a.size() > 4 else 20.0
		var outp: String = a[5] if a.size() > 5 else "res://mp_smoke.json"
		var err := peer.create_server(port, 32)
		if err != OK:
			printerr("[mp-smoke] cannot bind port %d (%d)" % [port, err])
			quit(2)
			return
		root.multiplayer.multiplayer_peer = peer
		smoke.setup_host(players - 1, secs, outp)
		print("[mp-smoke] host up on %d, expecting %d client(s)" % [port, players - 1])
	elif role == "client":
		var spawn := _v3(a[3]) if a.size() > 3 else Vector3.ZERO
		var tgt := _v3(a[4]) if a.size() > 4 else Vector3(10, 0, 0)
		var secs := float(a[5]) if a.size() > 5 else 20.0
		var err := peer.create_client("127.0.0.1", port)
		if err != OK:
			printerr("[mp-smoke] cannot create client (%d)" % err)
			quit(2)
			return
		root.multiplayer.multiplayer_peer = peer
		smoke.setup_client(spawn, tgt, secs)
	else:
		printerr("[mp-smoke] role must be host|client")
		quit(2)
		return

	# both sides load the site scene -- a load failure fails the smoke
	var packed: PackedScene = load(scene_path)
	if packed == null:
		printerr("[mp-smoke] cannot load %s (did the import pass run?)" % scene_path)
		quit(1)
		return
	var site: Node = packed.instantiate()
	root.add_child(site)
	print("[mp-smoke] %s loaded %s" % [role, scene_path])


static func _v3(s: String) -> Vector3:
	var p := s.split(",")
	return Vector3(float(p[0]), float(p[1]), float(p[2]))
