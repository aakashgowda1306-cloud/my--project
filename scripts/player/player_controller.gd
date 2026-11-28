class_name PlayerController
extends CharacterBody3D
## AFTERLIGHT — On-foot player controller (Phase 1).
##
## Responsibilities:
##   * Walk / jog / sprint movement relative to the camera direction.
##   * Jumping with "coyote time" and "jump buffering" so jumps feel fair.
##   * Gravity (heavier while falling, so jumps don't feel floaty).
##   * Stamina: sprinting and jumping cost stamina, it regenerates when resting.
##   * Turning the visible body (BodyPivot) toward where the player is moving.
##   * Respawning if the player falls out of the world.
##
## The physics body itself NEVER rotates — only the child node "BodyPivot" does.
## That keeps the collision capsule simple and lets the camera rotate freely.
##
## The camera is handled by camera_rig.gd. This script only asks the camera
## which way "forward" is, so the two systems stay independent.

signal stamina_changed(current: float, maximum: float)
signal exhausted_changed(is_exhausted: bool)
signal jumped
signal landed(impact_speed: float)
signal respawned

enum MoveState { IDLE, WALK, JOG, SPRINT, AIRBORNE }

@export_group("Speeds (metres per second)")
@export var walk_speed: float = 2.0
@export var jog_speed: float = 4.5
@export var sprint_speed: float = 7.5

@export_group("Acceleration")
## How fast we reach target speed on the ground (m/s²).
@export var ground_acceleration: float = 16.0
## How fast we stop when no key is held (m/s²).
@export var ground_deceleration: float = 20.0
## Small amount of steering while in the air (m/s²).
@export var air_acceleration: float = 4.0
## How quickly the body turns to face the movement direction.
@export var turn_speed: float = 12.0

@export_group("Jump and gravity")
@export var jump_velocity: float = 5.0
@export var gravity_multiplier: float = 1.0
## Extra gravity while falling makes jumps feel snappier and less floaty.
@export var fall_gravity_multiplier: float = 1.6
## Seconds after walking off a ledge where a jump is still allowed.
@export var coyote_time: float = 0.12
## Seconds a jump press is remembered before landing.
@export var jump_buffer_time: float = 0.12
## Falling below this height teleports the player back to the spawn point.
@export var respawn_height: float = -30.0

@export_group("Stamina")
@export var max_stamina: float = 100.0
@export var sprint_drain_per_sec: float = 18.0
@export var jump_stamina_cost: float = 8.0
@export var regen_per_sec: float = 22.0
## Seconds after spending stamina before it starts to regenerate.
@export var regen_delay: float = 0.8
## After hitting zero stamina, sprinting is locked until stamina reaches this value.
@export var exhausted_recover_threshold: float = 30.0

## Vehicles (Phase 2) and cutscenes will set this to false.
var input_enabled: bool = true
var stamina: float = 100.0
var is_exhausted: bool = false
var move_state: MoveState = MoveState.IDLE

var _gravity: float = 9.8
var _coyote_timer: float = 0.0
var _jump_buffer_timer: float = 0.0
var _regen_delay_timer: float = 0.0
var _spawn_transform: Transform3D
var _bob_time: float = 0.0

@onready var body_pivot: Node3D = $BodyPivot
@onready var body_mesh: Node3D = $BodyPivot/BodyMesh
@onready var camera_rig: CameraRig = $CameraRig


func _ready() -> void:
	add_to_group("player")
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))
	stamina = max_stamina
	_spawn_transform = global_transform
	# Keep the player glued to slopes and small bumps instead of "skipping" off them.
	floor_snap_length = 0.35
	floor_max_angle = deg_to_rad(46.0)
	floor_constant_speed = true


func _physics_process(delta: float) -> void:
	var on_floor := is_on_floor()

	# ---- Timers for forgiving jumps --------------------------------------
	if on_floor:
		_coyote_timer = coyote_time
	else:
		_coyote_timer -= delta
	_jump_buffer_timer -= delta
	if input_enabled and Input.is_action_just_pressed("jump"):
		_jump_buffer_timer = jump_buffer_time

	# ---- Gravity -----------------------------------------------------------
	if not on_floor:
		var mult := gravity_multiplier if velocity.y > 0.0 else fall_gravity_multiplier
		velocity.y -= _gravity * mult * delta

	# ---- Jump --------------------------------------------------------------
	if _jump_buffer_timer > 0.0 and _coyote_timer > 0.0:
		velocity.y = jump_velocity
		_jump_buffer_timer = 0.0
		_coyote_timer = 0.0
		_spend_stamina(jump_stamina_cost)
		jumped.emit()

	# ---- Read input --------------------------------------------------------
	var input_vec := Vector2.ZERO
	var wants_sprint := false
	var wants_walk := false
	if input_enabled:
		input_vec = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		wants_sprint = Input.is_action_pressed("sprint")
		wants_walk = Input.is_action_pressed("walk")

	# Convert 2D input to a 3D direction relative to where the camera looks.
	var wish_dir := camera_rig.get_flat_basis() * Vector3(input_vec.x, 0.0, input_vec.y)
	var has_input := wish_dir.length() > 0.05

	var can_sprint := wants_sprint and has_input and not is_exhausted and stamina > 0.0
	var target_speed := jog_speed
	if wants_walk:
		target_speed = walk_speed
	elif can_sprint:
		target_speed = sprint_speed

	# ---- Horizontal movement -----------------------------------------------
	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	var target_velocity := wish_dir * target_speed
	var accel: float
	if on_floor:
		accel = ground_acceleration if has_input else ground_deceleration
	else:
		accel = air_acceleration
	horizontal = horizontal.move_toward(target_velocity, accel * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z

	# ---- Stamina -----------------------------------------------------------
	if can_sprint and on_floor and not wants_walk:
		_spend_stamina(sprint_drain_per_sec * delta)
	else:
		_regenerate_stamina(delta)

	# ---- Move! -------------------------------------------------------------
	var fall_speed := -velocity.y
	move_and_slide()
	if not on_floor and is_on_floor():
		landed.emit(fall_speed)

	_update_body_rotation(horizontal, delta)
	_update_move_state(horizontal.length(), can_sprint, wants_walk)
	_update_body_bob(horizontal.length(), delta)

	if global_position.y < respawn_height:
		respawn()


## Teleports the player back to where they started (or a new spawn point).
func respawn(at: Transform3D = _spawn_transform) -> void:
	global_transform = at
	velocity = Vector3.ZERO
	stamina = max_stamina
	is_exhausted = false
	stamina_changed.emit(stamina, max_stamina)
	if has_method("reset_physics_interpolation"):
		reset_physics_interpolation()
	respawned.emit()


func set_spawn_point(t: Transform3D) -> void:
	_spawn_transform = t


func get_horizontal_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


func get_move_state_name() -> String:
	return MoveState.keys()[move_state]


# -------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------

func _spend_stamina(amount: float) -> void:
	if amount <= 0.0:
		return
	stamina = maxf(stamina - amount, 0.0)
	_regen_delay_timer = regen_delay
	if stamina <= 0.0 and not is_exhausted:
		is_exhausted = true
		exhausted_changed.emit(true)
	stamina_changed.emit(stamina, max_stamina)


func _regenerate_stamina(delta: float) -> void:
	if _regen_delay_timer > 0.0:
		_regen_delay_timer -= delta
		return
	if stamina >= max_stamina:
		return
	stamina = minf(stamina + regen_per_sec * delta, max_stamina)
	if is_exhausted and stamina >= exhausted_recover_threshold:
		is_exhausted = false
		exhausted_changed.emit(false)
	stamina_changed.emit(stamina, max_stamina)


func _update_body_rotation(horizontal: Vector3, delta: float) -> void:
	var target_yaw := body_pivot.rotation.y
	if camera_rig.is_first_person():
		# In first person the body always faces where you look.
		target_yaw = camera_rig.get_yaw()
	elif horizontal.length() > 0.2:
		# In third person the body turns toward the direction of travel.
		# Godot models face -Z, hence the minus signs.
		target_yaw = atan2(-horizontal.x, -horizontal.z)
	body_pivot.rotation.y = lerp_angle(body_pivot.rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))


func _update_move_state(speed: float, sprinting: bool, walking: bool) -> void:
	if not is_on_floor():
		move_state = MoveState.AIRBORNE
	elif speed < 0.15:
		move_state = MoveState.IDLE
	elif sprinting and not walking and speed > jog_speed + 0.2:
		move_state = MoveState.SPRINT
	elif speed <= walk_speed + 0.2:
		move_state = MoveState.WALK
	else:
		move_state = MoveState.JOG


## Placeholder "animation": a tiny vertical bob while moving, so motion reads
## clearly until real Blender animations replace the capsule in a later milestone.
func _update_body_bob(speed: float, delta: float) -> void:
	if body_mesh == null:
		return
	if is_on_floor() and speed > 0.2:
		_bob_time += delta * (6.0 + speed * 1.6)
		body_mesh.position.y = 0.88 + sin(_bob_time) * 0.025 * clampf(speed / jog_speed, 0.0, 1.5)
	else:
		body_mesh.position.y = lerpf(body_mesh.position.y, 0.88, clampf(10.0 * delta, 0.0, 1.0))
