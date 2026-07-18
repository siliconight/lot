extends Node3D
## lot_navqa_setup.gd -- bridges a Lot site to the Heist Nav QA addon.
## Generated alongside a *_navqa.tscn by `lot.py --navqa`. Lot bakes the heist's
## real anchors (crew/objective/loot/extraction as player proxies, cover points,
## cop spawns) into the arrays below as Godot-space Vector3s. On load this:
##   1. bakes the site NavigationRegion3D,
##   2. spawns Marker3D anchors into the addon's groups,
##   3. if the Heist Nav QA addon is installed, drops a director and runs it.
##
## Decoupled on purpose: if the addon isn't present the scene still opens and
## walks; you just get a warning instead of a bot run. Keeps Lot from depending
## on a third-party addon while still feeding it for free.

@export var player_proxies: PackedVector3Array = PackedVector3Array()
@export var cover_points: PackedVector3Array = PackedVector3Array()
@export var bot_spawns: PackedVector3Array = PackedVector3Array()
@export var crew_home: Vector3 = Vector3.ZERO   # director home / bot-ring center

# must match the addon's group exports (its defaults)
@export var player_proxy_group: String = "navqa_player_proxy"
@export var cover_group: String = "navqa_cover"
@export var bot_spawn_group: String = "navqa_bot_spawn"

@export var simulated_players: int = 4
@export var bot_count: int = 16
@export var run_on_ready: bool = true

const DIRECTOR_PATH := "res://addons/heist_nav_qa/nav_qa_director.gd"


func _ready() -> void:
	_bake_nav()
	_spawn_anchors(player_proxies, player_proxy_group, "Proxy")
	_spawn_anchors(cover_points, cover_group, "Cover")
	_spawn_anchors(bot_spawns, bot_spawn_group, "BotSpawn")
	if run_on_ready:
		_run_qa()


func _bake_nav() -> void:
	# the site is under a NavigationRegion3D named "Nav" (sibling, set up by Lot)
	var nav := get_node_or_null("../Nav") as NavigationRegion3D
	if nav == null:
		nav = get_tree().get_first_node_in_group("navigation_region") as NavigationRegion3D
	if nav and nav.navigation_mesh:
		# match the map's cell metrics to the mesh (mismatch causes edge
		# rasterization errors -- Godot warns about exactly this), then bake
		# SYNCHRONOUSLY: the QA run starts right after _ready, and an async
		# bake leaves the map empty under the first queries.
		var map: RID = get_world_3d().navigation_map
		NavigationServer3D.map_set_cell_size(map, nav.navigation_mesh.cell_size)
		NavigationServer3D.map_set_cell_height(map, nav.navigation_mesh.cell_height)
		nav.bake_navigation_mesh(false)
		# region updates are ASYNC on the NavigationServer -- the baked mesh
		# exists but the map's polygon soup commits on its own schedule.
		# Force the commit so the first queries see the real mesh.
		NavigationServer3D.map_force_update(map)
		print("[navqa-setup] bake done: %d polygons in navigation_mesh"
			% nav.navigation_mesh.get_polygon_count())
		var n_mesh := 0
		var stack: Array = [get_parent()]
		while not stack.is_empty():
			var nd: Node = stack.pop_back()
			if nd is MeshInstance3D:
				n_mesh += 1
			for c in nd.get_children():
				stack.append(c)
		print("[navqa-setup] scene has %d MeshInstance3D under root" % n_mesh)


func _spawn_anchors(points: PackedVector3Array, group: String, tag: String) -> void:
	for i in points.size():
		var m := Marker3D.new()
		m.name = "NavQA_%s_%d" % [tag, i]
		add_child(m)
		m.global_position = points[i]
		m.add_to_group(group)


func _run_qa() -> void:
	if not ResourceLoader.exists(DIRECTOR_PATH):
		push_warning("Heist Nav QA addon not found at %s -- install it to run the "
			% DIRECTOR_PATH + "bot QA. The site is still walkable.")
		return
	var director_script: Script = load(DIRECTOR_PATH)
	var director: Node3D = director_script.new()
	director.name = "NavQADirector"
	# configure to match the anchors we just spawned
	director.set("simulated_players", simulated_players)
	director.set("bot_count", bot_count)
	director.set("player_proxy_group", player_proxy_group)
	director.set("cover_group", cover_group)
	director.set("bot_spawn_group", bot_spawn_group)
	director.set("run_on_ready", false)
	# _run_qa executes during _ready, while the parent is still setting up
	# its children -- a plain add_child() fails ("parent node is busy").
	# Defer the add AND the start so both run after the tree settles, in
	# order (deferred calls execute FIFO).
	get_parent().add_child.call_deferred(director)
	_start_director.call_deferred(director)


func _start_director(director: Node3D) -> void:
	# home the director at the crew start so its fallbacks (bot ring / default
	# proxies) land in the right place if any group came up empty
	director.global_position = crew_home
	if director.has_method("start_qa_run"):
		director.call("start_qa_run")
