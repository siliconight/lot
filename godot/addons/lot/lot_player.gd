extends CharacterBody3D
## lot_player.gd -- a minimal first-person walker for site walk-throughs.
## Self-contained so a Lot site is walkable without the Deli Counter addon; if
## you'd rather use Deli Counter's harness player, delete this node from the
## *_walk.tscn and instance that one at the PlayerSpawn instead.
##
## Controls: WASD move, mouse look, Space jump, Shift sprint, Esc free cursor.

@export var speed := 5.0
@export var sprint := 8.5
@export var jump_velocity := 4.5
@export var mouse_sensitivity := 0.0025
## Max height the body auto-steps up in one move: curbs/sidewalks, ledges, and
## steep stair noses the capsule would otherwise catch on. Keep under ~0.5 m so
## you don't climb things you shouldn't. This is a raycast-probe step-up with a
## valid-direction + head-clearance check (after move_and_slide), adapted from
## the standard FPS step-climbing approach.
@export var max_step_height := 0.45
## Vertical climb speed on ladder volumes (m/s). The walk scene emits the
## Area3D climb volumes (group "ladder") from the site's gameplay ladder
## markers — same contract as Deli Counter's post-import.
@export var climb_speed := 3.0

var _cam: Camera3D
var _yaw := 0.0
var _pitch := 0.0


func _ready() -> void:
	_cam = get_node_or_null("Camera") as Camera3D
	if _cam == null:
		# build a camera at eye height if the scene didn't ship one
		_cam = Camera3D.new()
		_cam.name = "Camera"
		_cam.transform.origin = Vector3(0, 0.6, 0)
		add_child(_cam)
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch = clamp(_pitch - event.relative.y * mouse_sensitivity, -1.4, 1.4)
		rotation.y = _yaw
		if _cam:
			_cam.rotation.x = _pitch
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _physics_process(delta: float) -> void:
	# On a ladder climb volume? Climb instead of walking. Ported from Deli
	# Counter's reference player (template/player.gd): climb along where you
	# LOOK — look up + W to ascend, look down to descend, look level + W to
	# step off at the top. No input = cling (gravity off). Space drops.
	if _current_ladder() != null and not Input.is_key_pressed(KEY_SPACE):
		_climb(delta)
		return

	if not is_on_floor():
		velocity.y -= 9.8 * delta
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = jump_velocity

	var input_dir := Vector2(
		Input.get_axis("ui_left", "ui_right"),
		Input.get_axis("ui_up", "ui_down"))
	# WASD without relying on a project input map
	if Input.is_key_pressed(KEY_A): input_dir.x -= 1.0
	if Input.is_key_pressed(KEY_D): input_dir.x += 1.0
	if Input.is_key_pressed(KEY_W): input_dir.y -= 1.0
	if Input.is_key_pressed(KEY_S): input_dir.y += 1.0
	input_dir = input_dir.limit_length(1.0)

	var spd := sprint if Input.is_key_pressed(KEY_SHIFT) else speed
	var dir := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()
	velocity.x = dir.x * spd
	velocity.z = dir.z * spd
	_move_with_steps(delta)


func _move_with_steps(delta: float) -> void:
	# Normal move first. If grounded and walking into a short near-vertical
	# obstacle (curb, ledge, steep stair nose), lift onto it and continue --
	# CharacterBody3D has no built-in step handling.
	move_and_slide()
	if not is_on_floor():
		return
	var horiz := Vector3(velocity.x, 0.0, velocity.z)
	if horiz.length() < 0.05:
		return
	var into := horiz.normalized()

	# Only step if we're pushing INTO a near-vertical face, not sliding along it.
	var blocked := false
	for i in get_slide_collision_count():
		var col := get_slide_collision(i)
		if absf(col.get_normal().y) < 0.2 and into.dot(-col.get_normal()) > 0.3:
			blocked = true
			break
	if not blocked:
		return

	# Probe straight down from step height, just ahead, for the surface top.
	var space := get_world_3d().direct_space_state
	var ahead := into * 0.4
	var from := global_position + Vector3.UP * max_step_height + ahead
	var q := PhysicsRayQueryParameters3D.create(from, from - Vector3.UP * (max_step_height + 0.05))
	q.exclude = [get_rid()]
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return
	var step_top: float = hit["position"].y
	var rise := step_top - global_position.y
	if rise <= 0.02 or rise > max_step_height:
		return

	# Head clearance: don't climb into a low ceiling / under geometry.
	var hp: Vector3 = hit["position"]
	var head := PhysicsRayQueryParameters3D.create(
		Vector3(hp.x, step_top + 0.05, hp.z), Vector3(hp.x, step_top + 1.7, hp.z))
	head.exclude = [get_rid()]
	if not space.intersect_ray(head).is_empty():
		return

	# Lift onto the step and nudge forward past its riser.
	global_position.y = step_top + 0.02
	global_position += into * (speed * delta * 0.6)


func _current_ladder() -> Area3D:
	# Climb volumes are Area3Ds in the "ladder" group (emitted by the walk
	# scene from the site's gameplay ladder markers). We're "on" one if our
	# body overlaps it.
	for a in get_tree().get_nodes_in_group("ladder"):
		if a is Area3D and self in (a as Area3D).get_overlapping_bodies():
			return a
	return null


func _climb(_delta: float) -> void:
	# Move along the camera's look direction: look up + forward to ascend,
	# look down to descend, look level + forward to step off at the top.
	# Gravity is off here, so no input clings in place instead of sliding.
	var axis := Vector2.ZERO
	if Input.is_key_pressed(KEY_A): axis.x -= 1.0
	if Input.is_key_pressed(KEY_D): axis.x += 1.0
	if Input.is_key_pressed(KEY_W): axis.y -= 1.0
	if Input.is_key_pressed(KEY_S): axis.y += 1.0
	axis.x += Input.get_axis("ui_left", "ui_right")
	axis.y += Input.get_axis("ui_up", "ui_down")
	axis = axis.limit_length(1.0)
	var wish := -axis.y                # W / forward -> +1
	var look := -_cam.global_transform.basis.z if _cam else -transform.basis.z
	velocity = look * wish * climb_speed
	# small strafe so you can line up with the dismount at the top
	velocity += transform.basis.x * axis.x * (speed * 0.5)
	move_and_slide()
