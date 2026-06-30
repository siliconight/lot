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
		nav.bake_navigation_mesh()


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
	get_parent().add_child(director)
	# home the director at the crew start so its fallbacks (bot ring / default
	# proxies) land in the right place if any group came up empty
	director.global_position = crew_home
	if director.has_method("start_qa_run"):
		director.call("start_qa_run")
