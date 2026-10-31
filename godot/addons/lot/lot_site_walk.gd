extends Node3D
## lot_site_walk.gd -- run a Lot site as the heist crew.
## Generated alongside a *_walk.tscn by `lot.py --walkable`. Bakes a ground-level
## navigation mesh over the whole composed site (ground + buildings + outdoor),
## drops objective + extraction waypoints, and shows a tiny HUD. The player is a
## child of this scene already positioned at the crew spawn.
##
## The positions below are baked in by Lot at assemble time from the merged
## site gameplay (crew spawn / objective / extraction), so this script needs no
## JSON parsing at runtime.

@export var spawn_pos := Vector3.ZERO        # crew start (already where Player sits)
@export var objective_pos := Vector3.ZERO    # the loot/objective
@export var extraction_pos := Vector3.ZERO    # where the crew exits
@export var site_title := "SITE WALK"        # baked in by Lot (the site name)



func _ready() -> void:
	_bake_nav()
	_waypoint("OBJECTIVE", objective_pos, Color(1.0, 0.55, 0.1))
	_waypoint("EXTRACTION", extraction_pos, Color(0.2, 1.0, 0.5))
	var p := get_node_or_null("Player")
	if p:
		if DisplayServer.get_name() == "headless":
			# WHEN THERE IS NO WALKER, THE RIGHT NUMBER OF PLAYERS IS NONE --
			# the same reasoning `_bake_nav` already applies to baking.
			#
			# This node is a CharacterBody3D on collision layer 1 (the World
			# layer) with a 1.8 m capsule, and the line below parked it ON the
			# crew spawn -- which is the point of the preview and fatal to an
			# evaluation. Laser Tag spawns its own pill at that coordinate, so
			# the pill materialised INSIDE this capsule, was depenetrated onto
			# top of it, and came to rest 1.547 m above the navmesh with
			# is_on_floor() true. From there `get_next_path_position()` returns
			# the bot's own XZ, `_advance_route` flattens that to a zero vector,
			# and the body never takes a step.
			#
			# Measured on market_row_001 seed 7503, one run, same seed either
			# side: body_y 1.797 -> 0.001, gap to the navmesh +1.547 -> -0.499,
			# route index 0/3 -> 2/3, and a bot that had not moved in 10.7 s
			# walked ~20 m. Laser Tag's own demo greybox carries no such node,
			# which is why its bot always walked and this never showed up in
			# Laser Tag's CI.
			p.queue_free()
		else:
			p.global_position = spawn_pos
	_hud()


func _bake_nav() -> void:
	# Bake the site nav at load. The site geometry (ground + instanced buildings +
	# outdoor boxes) is a child of $Nav, so SOURCE_GEOMETRY_ROOT_NODE_CHILDREN
	# parses it.
	#
	# IF AI NAV LOOKS WRONG IN-ENGINE, these are the knobs (all on the NavMesh
	# resource in this scene):
	#   * geometry_parsed_geometry_type -- BOTH (default here) parses meshes AND
	#     static colliders. If building interiors don't carve out, try
	#     PARSED_GEOMETRY_STATIC_COLLIDERS (the .glb ships -colonly bodies).
	#   * cell_size / agent_radius / agent_height -- shrink cell_size for tighter
	#     doorways; agent_radius must clear the 1.0 m doors.
	#   * MULTI-FLOOR: a single baked region is ground-plane biased. Upper floors
	#     only join the graph if the stairs are bridged with nav-link anchors
	#     (the known Deli Counter multi-floor caveat). Ground traversal across the
	#     whole site is what this first walk proves.
	var nav := get_node_or_null("Nav") as NavigationRegion3D
	if nav == null or nav.navigation_mesh == null:
		return
	if DisplayServer.get_name() == "headless":
		# Nobody is walking this scene. Headless means it was loaded by an
		# evaluation runner (Laser Tag's map eval, CI) that bakes navigation
		# itself against its own agent parameters.
		#
		# bake_navigation_mesh() is threaded and returns immediately, so leaving
		# it running here does not just duplicate the runner's work -- it races
		# it. Godot refuses a second bake against a NavigationMesh that is
		# already baking, and the refused bake leaves a 0-polygon mesh that is
		# indistinguishable from a map with no collision at all. That is how a
		# fully walkable site came back as NAVIGATION_MISSING and burned 900
		# seconds watching bots walk into walls.
		#
		# When there is no walker, the right amount of baking is none.
		print("[lot] site_walk: headless — the evaluation runner owns the navmesh bake")
		return
	# the bake runs on a thread: the hidden states come back when it is done
	var parked := _park_hidden_states(nav)
	if not parked.is_empty():
		nav.bake_finished.connect(func() -> void: _unpark_states(parked), CONNECT_ONE_SHOT)
	nav.bake_navigation_mesh()


func _waypoint(label: String, pos: Vector3, col: Color) -> void:
	var holder := Node3D.new()
	holder.name = "WP_" + label
	holder.transform.origin = pos
	add_child(holder)
	# a thin tall beacon so you can see the objective/extraction from a distance
	var beam := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.25
	cyl.bottom_radius = 0.25
	cyl.height = 8.0
	beam.mesh = cyl
	beam.transform.origin = Vector3(0, 4.0, 0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mat.emission_enabled = true
	mat.emission = col
	mat.flags_transparent = true
	mat.albedo_color.a = 0.55
	beam.material_override = mat
	holder.add_child(beam)
	var tag := Label3D.new()
	tag.text = label
	tag.font_size = 96
	tag.modulate = col
	tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	tag.transform.origin = Vector3(0, 8.5, 0)
	holder.add_child(tag)


func _hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var lbl := Label.new()
	lbl.text = (site_title + "  —  you are the crew\n"
		+ "objective: reach the orange beacon\n"
		+ "then extract: green beacon\n"
		+ "WASD move · mouse look · Shift sprint · Space jump · Esc cursor")
	lbl.position = Vector2(16, 12)
	lbl.add_theme_color_override("font_color", Color(1, 1, 1))
	lbl.add_theme_font_size_override("font_size", 18)
	layer.add_child(lbl)


## HIDDEN STATES ARE NOT NAVIGATION (Lot 0.142.0). Godot's navmesh parse takes every MeshInstance3D under the region,
## visible or not -- `MeshInstance3D::navmesh_parse_source_geometry` checks no visibility -- and a composed building
## parks each interactive's other states HIDDEN at the same transform (Deli Counter's `themed_tscn`). So a shut vault
## door hidden behind a shown open one was a disc across the vault's mouth in the bake, and a hidden open leaf a wall
## in every shut vault. Every hidden node carrying `metadata/interactive_state` is set aside for the bake and put back
## where it was, at its own index. Returns what was set aside, for `_unpark_states`.
static func _park_hidden_states(root: Node) -> Array:
	var parked: Array = []
	var stack: Array = [root]
	while not stack.is_empty():
		var nd: Node = stack.pop_back()
		var n3 := nd as Node3D
		if n3 != null and n3.has_meta("interactive_state") and not n3.visible:
			parked.append([nd.get_parent(), nd, nd.get_index()])
			continue
		for c in nd.get_children():
			stack.append(c)
	for entry in parked:
		(entry[0] as Node).remove_child(entry[1] as Node)
	return parked


static func _unpark_states(parked: Array) -> void:
	parked.sort_custom(func(a: Array, b: Array) -> bool: return int(a[2]) < int(b[2]))
	for entry in parked:
		var parent := entry[0] as Node
		var nd := entry[1] as Node
		parent.add_child(nd)
		parent.move_child(nd, int(entry[2]))
