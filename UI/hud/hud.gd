extends CanvasLayer
## AFTERLIGHT — Phase 1 HUD.
##
## Shows:
##   * Stamina bar (bottom centre). Turns red while exhausted.
##   * Crosshair (only in first person).
##   * Debug panel (top left, toggle with F3): FPS, position, speed, state, camera.
##   * Controls help (bottom left).
##   * "Click to play" hint whenever the mouse is not captured.
##
## The HUD finds the player through the "player" group, so it does not need a
## hard-coded path and keeps working if the scene tree is rearranged.

@onready var debug_label: Label = $Root/DebugPanel/DebugLabel
@onready var debug_panel: Control = $Root/DebugPanel
@onready var stamina_bar: ProgressBar = $Root/StaminaBar
@onready var crosshair: Control = $Root/Crosshair
@onready var mouse_hint: Control = $Root/MouseHint

var _player: PlayerController
var _fill_style: StyleBoxFlat
const STAMINA_OK := Color(0.95, 0.72, 0.25)
const STAMINA_EXHAUSTED := Color(0.85, 0.25, 0.22)


func _ready() -> void:
	_fill_style = StyleBoxFlat.new()
	_fill_style.bg_color = STAMINA_OK
	_fill_style.set_corner_radius_all(3)
	stamina_bar.add_theme_stylebox_override("fill", _fill_style)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.45)
	bg.set_corner_radius_all(3)
	stamina_bar.add_theme_stylebox_override("background", bg)
	# The player may be added after the HUD, so look it up one frame later.
	_find_player.call_deferred()


func _find_player() -> void:
	_player = get_tree().get_first_node_in_group("player") as PlayerController
	if _player == null:
		push_warning("HUD: no node in group 'player' found.")
		return
	_player.stamina_changed.connect(_on_stamina_changed)
	_player.exhausted_changed.connect(_on_exhausted_changed)
	_on_stamina_changed(_player.stamina, _player.max_stamina)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_debug"):
		debug_panel.visible = not debug_panel.visible


func _process(_delta: float) -> void:
	mouse_hint.visible = Input.mouse_mode != Input.MOUSE_MODE_CAPTURED
	if _player == null:
		return
	var rig := _player.camera_rig
	crosshair.visible = rig.blend > 0.9
	if debug_panel.visible:
		var p := _player.global_position
		debug_label.text = "AFTERLIGHT  %s   |  Godot %s\nFPS: %d\nPosition: %.1f, %.1f, %.1f\nSpeed: %.2f m/s\nState: %s%s\nStamina: %d / %d\nCamera: %s (yaw %d°, pitch %d°)" % [
			ProjectSettings.get_setting("application/config/version", ""),
			Engine.get_version_info().string,
			Engine.get_frames_per_second(),
			p.x, p.y, p.z,
			_player.get_horizontal_speed(),
			_player.get_move_state_name(),
			"  (EXHAUSTED)" if _player.is_exhausted else "",
			int(_player.stamina), int(_player.max_stamina),
			"FIRST PERSON" if rig.is_first_person() else "THIRD PERSON",
			int(rad_to_deg(rig.get_yaw())), int(rad_to_deg(rig.get_pitch())),
		]


func _on_stamina_changed(current: float, maximum: float) -> void:
	stamina_bar.max_value = maximum
	stamina_bar.value = current


func _on_exhausted_changed(exhausted: bool) -> void:
	_fill_style.bg_color = STAMINA_EXHAUSTED if exhausted else STAMINA_OK
