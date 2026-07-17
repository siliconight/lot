extends SceneTree
# [WALK] night_strip first-person walk (lot v0.18.5). Staged into the lux
# project (walk/headless/) by tools/walk_night_strip.ps1 and run WINDOWED:
#
#   godot --path <lux> --script res://walk/headless/walk_night_strip.gd
#
# Assembles whatever the dress run staged — patina shells (or raw), dressing,
# the (branded) fixtures GLB — at the site transforms, bakes the merged site
# manifest through LuxRoot (streetlights and all), grades Blue Hour, and
# drops in a player.
#
#   WASD  move        SHIFT  sprint        SPACE  jump
#   F     cut/restore building power (the heist beat)
#   G     cycle grade (Blue Hour -> Gas Station Fluorescent -> Mission Goes Hot)
#   ESC   release mouse / click to grab    F8 quit
#
# --lf-selftest: build everything, print, quit (headless CI-ability).

const DIRP: String = "res://walk/headless"

# Blender (x, y) -> Godot (x, 0, -y). Sync with specs/night_strip.site.json.
# Footprint-true placement (v0.18.6): deli is a 38x38 corner-lot L, pawn
# 16x14, auto 26x18 — spacing derives from MEASURED bounds, fronts on the
# y_blender=2 sidewalk line, 6.7 m alleys between buildings.
const STORES: Array = [
	{"stems": ["night_deli.patina.glb", "night_deli.glb"], "extras": ["night_deli_dressing.glb"], "pos": Vector3(-34, 0, -21)},
	{"stems": ["night_pawn.patina.glb", "night_pawn.glb"], "extras": ["night_pawn_dressing.glb"], "pos": Vector3(0, 0, -9)},
	{"stems": ["night_auto.patina.glb", "night_auto.glb"], "extras": ["night_auto_dressing.glb"], "pos": Vector3(28, 0, -11)},
]

func _initialize() -> void:
	_main()

func _log(s: String) -> void:
	print("[WALK] " + s)

func _first_existing(cands: Array) -> String:
	for c in cands:
		if ResourceLoader.exists(DIRP + "/" + String(c)):
			return DIRP + "/" + String(c)
	return ""

func _main() -> void:
	await process_frame
	var selftest: bool = "--lf-selftest" in OS.get_cmdline_user_args()

	var stage: Node3D = Node3D.new()
	stage.name = "NightStripWalk"
	root.add_child(stage)

	# Ground: the staged set has no site ground plane — give the player one.
	var floor_body: StaticBody3D = StaticBody3D.new()
	var floor_shape: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(300, 1, 300)
	floor_shape.shape = box
	floor_body.add_child(floor_shape)
	floor_body.position = Vector3(0, -0.5, 0)
	var floor_mesh: MeshInstance3D = MeshInstance3D.new()
	var pm: PlaneMesh = PlaneMesh.new()
	pm.size = Vector2(300, 300)
	var fmat: StandardMaterial3D = StandardMaterial3D.new()
	fmat.albedo_color = Color(0.16, 0.16, 0.19)
	pm.material = fmat
	floor_mesh.mesh = pm
	floor_mesh.position = Vector3(0, 0.001, 0)
	stage.add_child(floor_body)
	stage.add_child(floor_mesh)

	var loaded: int = 0
	for s in STORES:
		var entry: Dictionary = s
		var shell: String = _first_existing(entry["stems"])
		if shell != "":
			var inst: Node3D = (load(shell) as PackedScene).instantiate() as Node3D
			stage.add_child(inst)
			inst.global_position = entry["pos"]
			loaded += 1
		for g in entry["extras"]:
			var p: String = _first_existing([g])
			if p != "":
				var d: Node3D = (load(p) as PackedScene).instantiate() as Node3D
				stage.add_child(d)
				d.global_position = entry["pos"]
	_log("stores loaded: " + str(loaded) + "/3")

	var fix_path: String = ""
	var lights_path: String = ""
	var d: DirAccess = DirAccess.open(DIRP)
	if d != null:
		for f in d.get_files():
			var fl: String = String(f)
			if fl.ends_with("_fixtures.glb"):
				fix_path = DIRP + "/" + fl
			elif fl.ends_with(".lights.json"):
				lights_path = DIRP + "/" + fl
	if fix_path != "":
		var fx: Node = (load(fix_path) as PackedScene).instantiate()
		stage.add_child(fx)  # site-space build: world transforms baked in
		_log("fixtures: " + fix_path.get_file())
	else:
		_log("WARN: no fixtures GLB staged — hardware will be missing")

	var lux: LuxRoot = LuxRoot.new()
	lux.name = "LuxRoot"
	stage.add_child(lux)
	await process_frame
	if lights_path != "":
		var bake: Dictionary = LuxLightLoader.bake(lights_path, stage)
		_log("bake: " + str(bake))
	else:
		_log("WARN: no site lights manifest staged — running unlit")
	lux.bind_fixture_emissives(stage)
	await process_frame
	lux.blend_to_preset(&"Blue Hour", 0.0)

	# Player: source-built controller, keycode-only (no input map needed).
	var src: String = _player_source()
	var script: GDScript = GDScript.new()
	script.source_code = src
	if script.reload() != OK:
		_log("FAIL: player script did not compile")
		quit(1)
		return
	var player: CharacterBody3D = CharacterBody3D.new()
	var col: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.height = 1.8
	cap.radius = 0.35
	col.shape = cap
	player.add_child(col)
	var head: Node3D = Node3D.new()
	head.name = "Head"
	head.position = Vector3(0, 0.75, 0)
	var cam: Camera3D = Camera3D.new()
	cam.fov = 75.0
	head.add_child(cam)
	player.add_child(head)
	player.set_script(script)
	player.position = Vector3(-52, 1.2, 1)   # west end of the strip, on the street
	stage.add_child(player)
	cam.current = true

	_log("walk ready — WASD move, F power cut, G grade, ESC mouse, F8 quit")
	if selftest:
		await process_frame
		_log("selftest ok")
		quit(0)


func _player_source() -> String:
	return """
extends CharacterBody3D

var yaw := 0.0
var pitch := 0.0
var grades := [&\"Blue Hour\", &\"Gas Station Fluorescent\", &\"Mission Goes Hot\"]
var grade_i := 0
var powered := true

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _lux() -> Node:
	return get_parent().get_node_or_null(^\"LuxRoot\")

func _input(e: InputEvent) -> void:
	if e is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= e.relative.x * 0.0022
		pitch = clampf(pitch - e.relative.y * 0.0022, -1.4, 1.4)
		rotation.y = yaw
		$Head.rotation.x = pitch
	if e is InputEventMouseButton and e.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if e is InputEventKey and e.pressed and not e.echo:
		match e.keycode:
			KEY_ESCAPE:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_F8:
				get_tree().quit()
			KEY_F:
				powered = not powered
				var l := _lux()
				if l != null:
					l.set_fixtures_powered(powered)
			KEY_G:
				grade_i = (grade_i + 1) % grades.size()
				var l2 := _lux()
				if l2 != null:
					l2.blend_to_preset(grades[grade_i], 0.6)

func _physics_process(delta: float) -> void:
	var dir := Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		dir -= transform.basis.z
	if Input.is_key_pressed(KEY_S):
		dir += transform.basis.z
	if Input.is_key_pressed(KEY_A):
		dir -= transform.basis.x
	if Input.is_key_pressed(KEY_D):
		dir += transform.basis.x
	dir.y = 0.0
	var speed := 7.5 if Input.is_key_pressed(KEY_SHIFT) else 4.0
	var flat := dir.normalized() * speed
	velocity.x = flat.x
	velocity.z = flat.z
	if not is_on_floor():
		velocity.y -= 18.0 * delta
	elif Input.is_key_pressed(KEY_SPACE):
		velocity.y = 6.5
	move_and_slide()
"""
