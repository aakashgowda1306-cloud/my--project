extends SceneTree
## AFTERLIGHT — Automated Phase 1 test suite.
##
## Runs the REAL main scene, simulates keyboard input, and checks that the
## player and camera behave as designed. No window is needed.
##
## Run from the project folder (Windows PowerShell example):
##   & "C:\Godot\Godot_v4.7.2-stable_win64_console.exe" --headless --path . --fixed-fps 60 -s res://tests/test_runner.gd
##
## Exit code 0 = all tests passed, 1 = at least one failed.

const MAIN_SCENE := "res://scenes/main/main.tscn"
const OPEN_GROUND := Vector3(0.0, 0.05, 0.0)  # centre of the crossroads: flat, open space

var _passed: int = 0
var _failed: int = 0
var _main: Node
var _player: PlayerController
var _rig: CameraRig


func _initialize() -> void:
	_run_all.call_deferred()


func _run_all() -> void:
	print("\n===== AFTERLIGHT Phase 1 tests (Godot %s) =====" % Engine.get_version_info().string)
	await _test_project_configuration()
	await _test_main_scene_loads()
	if _player == null:
		_finish()
		return
	await _test_player_lands_on_ground()
	await _test_jog_forward()
	await _test_sprint_faster_and_drains_stamina()
	await _test_walk_slower()
	await _test_stamina_regenerates()
	await _test_exhaustion_blocks_sprint()
	await _test_jump()
	await _test_jump_onto_1m_box_but_not_2m()
	await _test_camera_relative_movement()
	await _test_camera_toggle_first_person()
	await _test_camera_toggle_back_to_third_person()
	await _test_spring_arm_pulls_in_under_overhang()
	await _test_respawn_when_falling_out_of_world()
	_finish()


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------

func _test_project_configuration() -> void:
	var main_scene: String = ProjectSettings.get_setting("application/run/main_scene", "")
	check(main_scene == MAIN_SCENE, "main scene is %s" % MAIN_SCENE, "got '%s'" % main_scene)
	for action in ["move_forward", "move_back", "move_left", "move_right", "jump", "sprint",
			"walk", "toggle_camera", "interact", "camera_zoom_in", "camera_zoom_out",
			"ui_release_mouse", "toggle_debug"]:
		check(InputMap.has_action(action) and InputMap.action_get_events(action).size() > 0,
				"input action '%s' is mapped" % action)


func _test_main_scene_loads() -> void:
	var packed := load(MAIN_SCENE) as PackedScene
	check(packed != null, "main scene loads")
	if packed == null:
		return
	_main = packed.instantiate()
	root.add_child(_main)
	await wait_frames(2)
	_player = get_first_node_in_group("player") as PlayerController
	check(_player != null, "player exists and is in group 'player'")
	if _player == null:
		return
	_rig = _player.camera_rig
	check(_rig != null and _rig.camera.current, "player camera is the active camera")
	var spawn := _main.get_node("TestDistrict/PlayerSpawn") as Marker3D
	check(_player.global_position.distance_to(spawn.global_position) < 0.5,
			"player starts at PlayerSpawn marker")
	var generated := _main.get_node_or_null("TestDistrict/Generated")
	check(generated != null and generated.get_child_count() >= 5, "district blockout was generated")


func _test_player_lands_on_ground() -> void:
	await place_player(OPEN_GROUND + Vector3(0, 1.0, 0))
	await wait_physics(60)
	check(_player.is_on_floor(), "player falls and lands on the ground")
	check(absf(_player.global_position.y) < 0.1, "player feet rest at y≈0",
			"y=%.3f" % _player.global_position.y)


func _test_jog_forward() -> void:
	await place_player(OPEN_GROUND)
	var start := _player.global_position
	await hold(["move_forward"], 60)
	var moved := _player.global_position - start
	var speed := _player.get_horizontal_speed()
	release_all()
	# Camera yaw is 0, so "forward" is -Z.
	check(moved.z < -3.5 and absf(moved.x) < 0.1, "W moves the player forward (-Z) about 4 m in 1 s",
			"moved=%s" % moved)
	check(absf(speed - _player.jog_speed) < 0.2, "jog speed reaches %.1f m/s" % _player.jog_speed,
			"speed=%.2f" % speed)
	await wait_physics(30)
	check(_player.get_horizontal_speed() < 0.1, "player stops when the key is released")


func _test_sprint_faster_and_drains_stamina() -> void:
	await place_player(OPEN_GROUND)
	await hold(["move_forward", "sprint"], 60)
	var speed := _player.get_horizontal_speed()
	var state := _player.get_move_state_name()
	release_all()
	check(absf(speed - _player.sprint_speed) < 0.2, "sprint speed reaches %.1f m/s" % _player.sprint_speed,
			"speed=%.2f" % speed)
	check(state == "SPRINT", "move state is SPRINT while sprinting", "state=%s" % state)
	check(_player.stamina < _player.max_stamina - 10.0, "sprinting drains stamina",
			"stamina=%.1f" % _player.stamina)


func _test_walk_slower() -> void:
	await place_player(OPEN_GROUND)
	await hold(["move_forward", "walk"], 45)
	var speed := _player.get_horizontal_speed()
	release_all()
	check(absf(speed - _player.walk_speed) < 0.2, "walk speed (Ctrl) is %.1f m/s" % _player.walk_speed,
			"speed=%.2f" % speed)


func _test_stamina_regenerates() -> void:
	_player.stamina = 40.0
	_player.is_exhausted = false
	await wait_physics(60 * 3)
	check(_player.stamina > 80.0, "stamina regenerates while resting", "stamina=%.1f" % _player.stamina)


func _test_exhaustion_blocks_sprint() -> void:
	await place_player(OPEN_GROUND)
	_player.stamina = 5.0
	await hold(["move_forward", "sprint"], 60)
	var speed := _player.get_horizontal_speed()
	var exhausted := _player.is_exhausted
	release_all()
	check(exhausted, "running out of stamina makes the player exhausted")
	check(absf(speed - _player.jog_speed) < 0.3, "an exhausted player can only jog",
			"speed=%.2f" % speed)
	await wait_physics(60 * 3)
	check(not _player.is_exhausted, "exhaustion wears off after resting")


func _test_jump() -> void:
	await place_player(OPEN_GROUND)
	await wait_physics(10)
	var start_y := _player.global_position.y
	var peak := start_y
	Input.action_press("jump")
	await wait_physics(2)
	Input.action_release("jump")
	var left_floor := false
	for i in 90:
		await physics_frame
		peak = maxf(peak, _player.global_position.y)
		if not _player.is_on_floor():
			left_floor = true
	var h := peak - start_y
	check(left_floor, "Space makes the player leave the ground")
	# Expected peak: v² / (2g) = 5² / (2 * 9.8) ≈ 1.28 m
	check(h > 1.1 and h < 1.45, "jump height is about 1.28 m", "height=%.2f" % h)
	check(_player.is_on_floor(), "player lands again after the jump")


func _test_jump_onto_1m_box_but_not_2m() -> void:
	# Jump boxes are in the Test Yard at local (4 + i*4, 4) with heights 0.5/1/1.5/2.
	var yard := _main.get_node("TestDistrict/Generated/TestYard") as Node3D
	var box_1m := yard.to_global(Vector3(8.0, 0.0, 4.0))
	var box_2m := yard.to_global(Vector3(16.0, 0.0, 4.0))
	check(await _try_jump_onto(box_1m) > 0.9, "player can jump onto the 1.0 m box")
	check(await _try_jump_onto(box_2m) < 0.5, "player cannot jump onto the 2.0 m box")


## Starts 3 m south of a box, runs north, jumps, and returns the height reached.
func _try_jump_onto(box_base: Vector3) -> float:
	await place_player(box_base + Vector3(0, 0.05, 3.0))
	Input.action_press("move_forward")
	await wait_physics(24)
	Input.action_press("jump")
	await wait_physics(2)
	Input.action_release("jump")
	await wait_physics(30)
	release_all()
	await wait_physics(60)
	return _player.global_position.y


func _test_camera_relative_movement() -> void:
	await place_player(OPEN_GROUND)
	_rig.set_yaw(deg_to_rad(90.0))  # look left (-X)
	var start := _player.global_position
	await hold(["move_forward"], 45)
	release_all()
	var moved := _player.global_position - start
	check(moved.x < -2.0 and absf(moved.z) < 0.2, "W follows the camera: looking left moves toward -X",
			"moved=%s" % moved)
	await wait_physics(30)
	# In third person the body turns toward the movement direction.
	var body_yaw := wrapf(_player.body_pivot.rotation.y, -PI, PI)
	check(absf(angle_difference(body_yaw, deg_to_rad(90.0))) < deg_to_rad(10.0),
			"body turns to face the direction of travel", "yaw=%.1f°" % rad_to_deg(body_yaw))
	_rig.set_yaw(0.0)


func _test_camera_toggle_first_person() -> void:
	await place_player(OPEN_GROUND)
	check(not _rig.is_first_person(), "game starts in third person")
	var tp_cam_dist := _rig.camera.global_position.distance_to(_player.global_position + Vector3(0, _rig.tp_height, 0))
	check(tp_cam_dist > 2.5, "third-person camera sits behind the player", "dist=%.2f" % tp_cam_dist)
	await press_action_event("toggle_camera")
	check(_rig.is_first_person(), "pressing V switches to first person")
	await wait_frames(3)
	check(_rig.blend > 0.0 and _rig.blend < 1.0, "the switch is a smooth blend, not a cut",
			"blend=%.2f" % _rig.blend)
	await wait_frames(40)
	check(is_equal_approx(_rig.blend, 1.0), "blend completes within %.2f s" % _rig.transition_time)
	var eye := _player.global_position + Vector3(0, _rig.fp_height, 0)
	var fp_dist := _rig.camera.global_position.distance_to(eye)
	check(fp_dist < 0.3, "first-person camera is at eye height", "dist=%.2f" % fp_dist)
	check(not _rig.camera.get_cull_mask_value(_rig.body_render_layer),
			"own body is hidden from the first-person camera")
	# In first person the body faces where the camera looks.
	_rig.set_yaw(deg_to_rad(-45.0))
	await wait_physics(40)
	check(absf(angle_difference(_player.body_pivot.rotation.y, deg_to_rad(-45.0))) < deg_to_rad(5.0),
			"in first person the body turns with the camera")
	_rig.set_yaw(0.0)


func _test_camera_toggle_back_to_third_person() -> void:
	await press_action_event("toggle_camera")
	await wait_frames(40)
	check(not _rig.is_first_person() and is_equal_approx(_rig.blend, 0.0), "pressing V again returns to third person")
	check(_rig.camera.get_cull_mask_value(_rig.body_render_layer), "body is visible again in third person")


func _test_spring_arm_pulls_in_under_overhang() -> void:
	# The overhang roof is at Test Yard local (36, 2.4 .. 2.9, 14), 8 x 10 m.
	var yard := _main.get_node("TestDistrict/Generated/TestYard") as Node3D
	await place_player(yard.to_global(Vector3(36.0, 0.05, 14.0)))
	_rig.add_look_input(Vector2(0.0, deg_to_rad(-40.0)))  # look down: camera swings up toward the roof
	await wait_physics(10)
	await wait_frames(5)
	var cam_y := _rig.camera.global_position.y
	check(cam_y < 2.4, "camera stays below the overhang roof (no clipping)", "camera y=%.2f" % cam_y)
	_rig.add_look_input(Vector2(0.0, deg_to_rad(40.0)))


func _test_respawn_when_falling_out_of_world() -> void:
	var spawn := _main.get_node("TestDistrict/PlayerSpawn") as Marker3D
	_player.global_position = Vector3(0, _player.respawn_height - 5.0, 0)
	await wait_physics(3)
	check(_player.global_position.distance_to(spawn.global_position) < 0.5,
			"falling out of the world respawns the player at PlayerSpawn")


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

func check(condition: bool, description: String, detail: String = "") -> void:
	if condition:
		_passed += 1
		print("  PASS  %s" % description)
	else:
		_failed += 1
		printerr("  FAIL  %s  %s" % [description, ("(" + detail + ")") if detail != "" else ""])


func place_player(pos: Vector3) -> void:
	release_all()
	_player.global_position = pos
	_player.velocity = Vector3.ZERO
	_player.stamina = _player.max_stamina
	_player.is_exhausted = false
	if _player.has_method("reset_physics_interpolation"):
		_player.reset_physics_interpolation()
	await wait_physics(15)


func hold(actions: Array, frames: int) -> void:
	for a in actions:
		Input.action_press(a)
	await wait_physics(frames)


func release_all() -> void:
	for a in ["move_forward", "move_back", "move_left", "move_right", "jump", "sprint", "walk"]:
		Input.action_release(a)


## Sends a real InputEventAction through the input pipeline (like a key press).
func press_action_event(action: String) -> void:
	var down := InputEventAction.new()
	down.action = action
	down.pressed = true
	Input.parse_input_event(down)
	await wait_frames(1)
	var up := InputEventAction.new()
	up.action = action
	up.pressed = false
	Input.parse_input_event(up)
	await wait_frames(1)


func wait_physics(n: int) -> void:
	for i in n:
		await physics_frame


func wait_frames(n: int) -> void:
	for i in n:
		await process_frame


func _finish() -> void:
	release_all()
	print("===== %d passed, %d failed =====\n" % [_passed, _failed])
	if _main:
		_main.queue_free()
	quit(1 if _failed > 0 else 0)
