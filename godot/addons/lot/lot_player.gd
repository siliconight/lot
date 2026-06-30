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
	move_and_slide()
