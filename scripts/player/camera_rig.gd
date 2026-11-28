class_name CameraRig
extends Node3D
## AFTERLIGHT — Player camera rig (Phase 1).
##
## Node layout (see scenes/player/player.tscn):
##   CameraRig (this script, yaw = left/right look)
##   └─ Pitch            (up/down look)
##      └─ SpringArm3D   (pulls the camera in when a wall is behind the player)
##         └─ Camera3D
##
## Features:
##   * Mouse look with pitch limits.
##   * Third-person over-the-shoulder view with wall collision (SpringArm3D).
##   * First-person view. Press V to switch; the change is a smooth blend.
##   * Mouse-wheel zoom in third person.
##   * Esc frees the mouse; clicking the game window captures it again.
##
## The rig is "top_level", so it does not inherit the player's transform.
## Each frame it moves itself to the player's (interpolated) position. This
## avoids camera jitter on high-refresh-rate monitors.

signal mode_changed(first_person: bool)

@export_group("Mouse")
@export var mouse_sensitivity: float = 0.0025
@export var invert_y: bool = false

@export_group("Third person")
@export var tp_distance: float = 3.6
@export var tp_min_distance: float = 1.8
@export var tp_max_distance: float = 7.0
@export var tp_zoom_step: float = 0.5
## Height of the camera pivot above the player's feet.
@export var tp_height: float = 1.6
## Sideways offset so the player is not blocking the centre of the screen.
@export var tp_shoulder_offset: float = 0.45
@export var tp_fov: float = 70.0
@export var tp_pitch_min_deg: float = -70.0
@export var tp_pitch_max_deg: float = 55.0

@export_group("First person")
## Eye height above the player's feet.
@export var fp_height: float = 1.65
## Moves the camera slightly forward so it sits at the face, not inside the head.
@export var fp_forward_offset: float = 0.12
@export var fp_fov: float = 75.0
@export var fp_pitch_min_deg: float = -85.0
@export var fp_pitch_max_deg: float = 85.0

@export_group("Transition")
## Seconds it takes to blend between third and first person.
@export var transition_time: float = 0.35
## Render layer holding the player's body meshes (hidden in first person).
@export_range(1, 20) var body_render_layer: int = 2

var first_person: bool = false
## 0.0 = fully third person, 1.0 = fully first person.
var blend: float = 0.0

var _target: Node3D
var _yaw: float = 0.0
var _pitch: float = deg_to_rad(-10.0)

@onready var pitch_node: Node3D = $Pitch
@onready var spring_arm: SpringArm3D = $Pitch/SpringArm3D
@onready var camera: Camera3D = $Pitch/SpringArm3D/Camera3D


func _ready() -> void:
	_target = get_parent() as Node3D
	top_level = true
	# We place this node ourselves every frame, so physics interpolation must
	# not also try to smooth it (that would add lag).
	if "physics_interpolation_mode" in self:
		set("physics_interpolation_mode", Node.PHYSICS_INTERPOLATION_MODE_OFF)
	if _target is CollisionObject3D:
		spring_arm.add_excluded_object((_target as CollisionObject3D).get_rid())
	_yaw = _target.global_rotation.y if _target else 0.0
	camera.current = true
	capture_mouse()
	_apply_blend()
	_follow_target()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion := event as InputEventMouseMotion
		var y_sign := -1.0 if invert_y else 1.0
		add_look_input(Vector2(-motion.relative.x, -motion.relative.y * y_sign) * mouse_sensitivity)
	elif event.is_action_pressed("toggle_camera"):
		toggle_mode()
	elif event.is_action_pressed("camera_zoom_in") and not first_person:
		tp_distance = clampf(tp_distance - tp_zoom_step, tp_min_distance, tp_max_distance)
	elif event.is_action_pressed("camera_zoom_out") and not first_person:
		tp_distance = clampf(tp_distance + tp_zoom_step, tp_min_distance, tp_max_distance)
	elif event.is_action_pressed("ui_release_mouse"):
		release_mouse()
	elif event is InputEventMouseButton and event.pressed \
			and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		capture_mouse()


func _process(delta: float) -> void:
	var target_blend := 1.0 if first_person else 0.0
	if not is_equal_approx(blend, target_blend):
		var step := delta / maxf(transition_time, 0.001)
		blend = move_toward(blend, target_blend, step)
	_apply_blend()
	_follow_target()


## Adds yaw (x) and pitch (y) in radians. Used by the mouse, and later by gamepads.
func add_look_input(look: Vector2) -> void:
	_yaw = wrapf(_yaw + look.x, -PI, PI)
	_pitch += look.y
	_clamp_pitch()
	rotation = Vector3(0.0, _yaw, 0.0)
	pitch_node.rotation = Vector3(_pitch, 0.0, 0.0)


func set_yaw(yaw_radians: float) -> void:
	_yaw = wrapf(yaw_radians, -PI, PI)
	rotation = Vector3(0.0, _yaw, 0.0)


func get_yaw() -> float:
	return _yaw


func get_pitch() -> float:
	return _pitch


## A basis that only contains the left/right look direction. The player uses
## it to turn "W" into "walk where the camera is facing", ignoring pitch.
func get_flat_basis() -> Basis:
	return Basis(Vector3.UP, _yaw)


func is_first_person() -> bool:
	return first_person


func toggle_mode() -> void:
	set_first_person(not first_person)


func set_first_person(enabled: bool) -> void:
	if enabled == first_person:
		return
	first_person = enabled
	_clamp_pitch()
	mode_changed.emit(first_person)


func capture_mouse() -> void:
	# Headless test runs have no real mouse; capturing there is harmless.
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func release_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


# -------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------

func _clamp_pitch() -> void:
	var min_deg := lerpf(tp_pitch_min_deg, fp_pitch_min_deg, 1.0 if first_person else 0.0)
	var max_deg := lerpf(tp_pitch_max_deg, fp_pitch_max_deg, 1.0 if first_person else 0.0)
	_pitch = clampf(_pitch, deg_to_rad(min_deg), deg_to_rad(max_deg))
	if pitch_node:
		pitch_node.rotation = Vector3(_pitch, 0.0, 0.0)


func _apply_blend() -> void:
	# smoothstep gives an ease-in/ease-out feel instead of a linear slide.
	var t := smoothstep(0.0, 1.0, blend)
	spring_arm.spring_length = lerpf(tp_distance, 0.0, t)
	# Note: SpringArm3D overwrites its child camera's position every frame, so
	# the shoulder and first-person forward offsets are applied to the arm itself.
	# The arm sits under "Pitch", so its local -Z is the direction we look.
	spring_arm.position = Vector3(lerpf(tp_shoulder_offset, 0.0, t), 0.0, lerpf(0.0, -fp_forward_offset, t))
	camera.fov = lerpf(tp_fov, fp_fov, t)
	# Hide our own body once the camera is (nearly) inside the head.
	camera.set_cull_mask_value(body_render_layer, t < 0.85)


func _follow_target() -> void:
	if _target == null:
		return
	var origin: Vector3
	if _target.has_method("get_global_transform_interpolated"):
		origin = _target.get_global_transform_interpolated().origin
	else:
		origin = _target.global_position
	var height := lerpf(tp_height, fp_height, smoothstep(0.0, 1.0, blend))
	global_position = origin + Vector3(0.0, height, 0.0)
	rotation = Vector3(0.0, _yaw, 0.0)
