extends Node3D
## AFTERLIGHT — Main scene bootstrap (Phase 1).
##
## Keeps the main scene simple: it moves the player to the district's
## "PlayerSpawn" marker and remembers that spot as the respawn point.
## Later milestones will grow this into a proper GameManager (save/load,
## world streaming, mission state) — but only when we actually need it.

@onready var player: PlayerController = $Player
@onready var district: Node3D = $TestDistrict


func _ready() -> void:
	var spawn := district.get_node_or_null("PlayerSpawn") as Marker3D
	if spawn:
		player.respawn(spawn.global_transform)
		player.set_spawn_point(spawn.global_transform)
	else:
		push_warning("Main: TestDistrict has no PlayerSpawn marker; using the player's scene position.")
	print("AFTERLIGHT %s started on Godot %s" % [
		ProjectSettings.get_setting("application/config/version", "?"),
		Engine.get_version_info().string,
	])
