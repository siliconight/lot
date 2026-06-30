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


func _ready() -> void:
	_bake_nav()
	_waypoint("OBJECTIVE", objective_pos, Color(1.0, 0.55, 0.1))
	_waypoint("EXTRACTION", extraction_pos, Color(0.2, 1.0, 0.5))
	var p := get_node_or_null("Player")
	if p:
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
	if nav and nav.navigation_mesh:
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
	lbl.text = ("VAULT JOB  —  you are the crew\n"
		+ "objective: reach the orange beacon (the vault)\n"
		+ "then extract: green beacon\n"
		+ "WASD move · mouse look · Shift sprint · Space jump · Esc cursor")
	lbl.position = Vector2(16, 12)
	lbl.add_theme_color_override("font_color", Color(1, 1, 1))
	lbl.add_theme_font_size_override("font_size", 18)
	layer.add_child(lbl)
