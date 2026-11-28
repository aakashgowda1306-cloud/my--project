@tool
class_name DistrictBlockout
extends Node3D
## AFTERLIGHT — Nova City "Founders Cross" blockout (Phase 1 test district).
##
## Builds a placeholder city block out of simple boxes at load time:
##   * A crossroads with lane markings and sidewalks.
##   * Four city blocks: Downtown towers, Mid-rise offices, a low-rise
##     residential corner with a small park, and the "Test Yard".
##   * The Test Yard contains jump boxes, ramps, stairs, an unclimbable steep
##     slope and a low overhang — everything needed to verify movement and
##     camera collision.
##
## Why boxes? In professional studios this step is called "greyboxing" or
## "blockout": you prove that scale, movement and camera feel right with cheap
## geometry BEFORE spending weeks on Blender art. The real Blender buildings
## will replace these boxes later without changing the gameplay code.
##
## "@tool" means this script also runs inside the Godot editor, so you can see
## the city in the 3D viewport. The generated nodes are NOT saved into the
## .tscn file — they are rebuilt every time the scene loads. Change a number
## below (e.g. the seed) and press "Rebuild" in the Inspector to see the effect.

const GRID_SHADER := preload("res://shaders/blockout_grid.gdshader")

## Change the seed to get a different (but repeatable) skyline.
@export var city_seed: int = 2042:
	set(value):
		city_seed = value
		_queue_rebuild()
## Half the width of the playable square, in metres.
@export var half_extent: float = 120.0
@export var road_half_width: float = 6.0
@export var sidewalk_width: float = 4.0
## Tick this in the Inspector to rebuild the blockout inside the editor.
@export var rebuild: bool = false:
	set(value):
		rebuild = false
		_queue_rebuild()

## Colours for each surface type (albedo, grid line).
const PALETTE := {
	"ground": [Color(0.30, 0.31, 0.29), Color(0.22, 0.23, 0.21)],
	"asphalt": [Color(0.13, 0.135, 0.145), Color(0.13, 0.135, 0.145)],
	"sidewalk": [Color(0.44, 0.43, 0.41), Color(0.34, 0.33, 0.31)],
	"park": [Color(0.24, 0.38, 0.20), Color(0.19, 0.30, 0.16)],
	"downtown": [Color(0.30, 0.36, 0.44), Color(0.20, 0.24, 0.30)],
	"midrise": [Color(0.48, 0.43, 0.37), Color(0.34, 0.30, 0.25)],
	"residential": [Color(0.55, 0.38, 0.30), Color(0.40, 0.27, 0.21)],
	"testyard": [Color(0.70, 0.48, 0.15), Color(0.45, 0.30, 0.08)],
	"testyard_alt": [Color(0.20, 0.42, 0.55), Color(0.12, 0.27, 0.36)],
	"danger": [Color(0.62, 0.16, 0.14), Color(0.38, 0.09, 0.08)],
	"line_white": [Color(0.78, 0.78, 0.74), Color(0.78, 0.78, 0.74)],
	"line_yellow": [Color(0.80, 0.60, 0.10), Color(0.80, 0.60, 0.10)],
}

var _materials: Dictionary = {}
var _rebuild_queued: bool = false


func _ready() -> void:
	build()


func _queue_rebuild() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	_deferred_build.call_deferred()


func _deferred_build() -> void:
	_rebuild_queued = false
	build()


## Removes the old generated geometry and builds it all again.
func build() -> void:
	for child in get_children():
		if child.has_meta("generated"):
			remove_child(child)
			child.queue_free()
	_materials.clear()

	var rng := RandomNumberGenerator.new()
	rng.seed = city_seed

	var root := Node3D.new()
	root.name = "Generated"
	root.set_meta("generated", true)
	add_child(root)

	_build_ground(root)
	_build_roads(root)
	_build_blocks(root, rng)
	_build_test_yard(root)
	_build_world_bounds(root)


# -------------------------------------------------------------------------
# Ground, roads and sidewalks
# -------------------------------------------------------------------------

func _build_ground(root: Node3D) -> void:
	var size := half_extent * 2.0
	# Top surface of the ground is exactly y = 0.
	add_box(root, "Ground", Vector3(0, -0.5, 0), Vector3(size, 1.0, size), "ground")


func _build_roads(root: Node3D) -> void:
	var roads := Node3D.new()
	roads.name = "Roads"
	root.add_child(roads)
	var length := half_extent * 2.0
	var rw := road_half_width * 2.0
	# Roads and markings are visual only (the Ground box already gives collision).
	# Each layer sits a few millimetres higher than the one below to avoid flicker.
	add_box(roads, "RoadEastWest", Vector3(0, 0.005, 0), Vector3(length, 0.01, rw), "asphalt", Vector3.ZERO, false)
	add_box(roads, "RoadNorthSouth", Vector3(0, 0.006, 0), Vector3(rw, 0.01, length), "asphalt", Vector3.ZERO, false)

	var sw_offset := road_half_width + sidewalk_width * 0.5
	for s in [-1.0, 1.0]:
		add_box(roads, "SidewalkEW", Vector3(0, 0.004, s * sw_offset), Vector3(length, 0.01, sidewalk_width), "sidewalk", Vector3.ZERO, false)
		add_box(roads, "SidewalkNS", Vector3(s * sw_offset, 0.003, 0), Vector3(sidewalk_width, 0.01, length), "sidewalk", Vector3.ZERO, false)

	# Lane markings: dashed white centre lines, skipping the intersection.
	var dash := 3.0
	var gap := 3.0
	var start := road_half_width + sidewalk_width + 2.0
	var d := start
	while d < half_extent - dash:
		for s in [-1.0, 1.0]:
			var c: float = s * (d + dash * 0.5)
			add_box(roads, "DashEW", Vector3(c, 0.012, 0), Vector3(dash, 0.005, 0.15), "line_white", Vector3.ZERO, false)
			add_box(roads, "DashNS", Vector3(0, 0.012, c), Vector3(0.15, 0.005, dash), "line_white", Vector3.ZERO, false)
		d += dash + gap
	# Yellow stop lines at the intersection.
	for s in [-1.0, 1.0]:
		add_box(roads, "StopEW", Vector3(s * (road_half_width + 0.5), 0.013, 0), Vector3(0.4, 0.005, road_half_width * 2.0), "line_yellow", Vector3.ZERO, false)
		add_box(roads, "StopNS", Vector3(0, 0.013, s * (road_half_width + 0.5)), Vector3(road_half_width * 2.0, 0.005, 0.4), "line_yellow", Vector3.ZERO, false)


# -------------------------------------------------------------------------
# City blocks
# -------------------------------------------------------------------------

## Each quadrant is split into a 4 x 4 grid of lots separated by alleys.
## quadrant sign: (x_sign, z_sign). Remember: -Z is "north" (camera forward).
func _build_blocks(root: Node3D, rng: RandomNumberGenerator) -> void:
	var quadrants := [
		{"name": "Downtown", "sign": Vector2(1, -1), "style": "downtown", "h_min": 30.0, "h_max": 90.0},
		{"name": "Midrise", "sign": Vector2(-1, -1), "style": "midrise", "h_min": 12.0, "h_max": 36.0},
		{"name": "Residential", "sign": Vector2(-1, 1), "style": "residential", "h_min": 6.0, "h_max": 14.0},
		{"name": "TestYardBlock", "sign": Vector2(1, 1), "style": "midrise", "h_min": 10.0, "h_max": 24.0},
	]
	var lot := 20.0
	var alley := 6.0
	var first := road_half_width + sidewalk_width + 2.0  # gap between sidewalk and first lot

	for q in quadrants:
		var holder := Node3D.new()
		holder.name = q.name
		root.add_child(holder)
		for ix in 4:
			for iz in 4:
				var cx: float = q.sign.x * (first + lot * 0.5 + ix * (lot + alley))
				var cz: float = q.sign.y * (first + lot * 0.5 + iz * (lot + alley))
				# The 2 x 2 lots nearest the crossroads in the south-east block are the Test Yard.
				if q.name == "TestYardBlock" and ix < 2 and iz < 2:
					continue
				# A small park in the residential block.
				if q.name == "Residential" and ix == 1 and iz == 0:
					add_box(holder, "Park", Vector3(cx, 0.02, cz), Vector3(lot, 0.04, lot), "park", Vector3.ZERO, false)
					continue
				var inset := rng.randf_range(0.0, 3.0)
				var w := lot - inset * 2.0
				var dd := lot - rng.randf_range(0.0, 3.0) * 2.0
				var h := rng.randf_range(q.h_min, q.h_max)
				# Taller buildings toward the crossroads in Downtown, for a skyline.
				if q.name == "Downtown":
					h *= lerpf(1.2, 0.7, float(ix + iz) / 6.0)
				add_box(holder, "Building", Vector3(cx, h * 0.5, cz), Vector3(w, h, dd), q.style)
				# Some towers get a narrower top section.
				if h > 40.0 and rng.randf() < 0.6:
					var h2 := rng.randf_range(8.0, 25.0)
					add_box(holder, "Crown", Vector3(cx, h + h2 * 0.5, cz), Vector3(w * 0.6, h2, dd * 0.6), q.style)


# -------------------------------------------------------------------------
# Test Yard — a movement & camera test course
# -------------------------------------------------------------------------

func _build_test_yard(root: Node3D) -> void:
	var yard := Node3D.new()
	yard.name = "TestYard"
	# The yard starts just past the south-east sidewalk corner.
	var o := road_half_width + sidewalk_width + 2.0
	yard.position = Vector3(o, 0, o)
	root.add_child(yard)
	# The yard is 46 x 46 m (two lots plus the alley between them).

	# Jump boxes of increasing height (0.5 m .. 2.0 m). With the default
	# jump the player can reach about 1.25 m, so the 1.5 m and 2 m boxes
	# should NOT be reachable — that is part of the test.
	var heights := [0.5, 1.0, 1.5, 2.0]
	for i in heights.size():
		var h: float = heights[i]
		add_box(yard, "JumpBox_%.1fm" % h, Vector3(4.0 + i * 4.0, h * 0.5, 4.0), Vector3(2.5, h, 2.5),
				"testyard" if i % 2 == 0 else "testyard_alt")

	# Ramps (15°, 30°) that should be walkable, and a 55° slope that should not.
	_add_ramp(yard, "Ramp_15deg", Vector3(4.0, 0, 22.0), 15.0, 10.0, 4.0, "testyard")
	_add_ramp(yard, "Ramp_30deg", Vector3(10.0, 0, 22.0), 30.0, 8.0, 4.0, "testyard_alt")
	_add_ramp(yard, "Slope_55deg_TooSteep", Vector3(16.0, 0, 22.0), 55.0, 6.0, 4.0, "danger")

	# Stairs: 10 steps of 0.2 m. The steps you SEE are separate from the
	# collision: one invisible ramp lets the capsule glide up smoothly. This is
	# a standard trick in third-person games.
	var stairs := Node3D.new()
	stairs.name = "Stairs"
	stairs.position = Vector3(24.0, 0, 26.0)
	yard.add_child(stairs)
	var rise := 0.2
	var run := 0.35
	var steps := 10
	for i in steps:
		var top := rise * (i + 1)
		add_box(stairs, "Step", Vector3(0, top * 0.5, -run * (i + 0.5)), Vector3(3.0, top, run), "testyard_alt", Vector3.ZERO, false)
	var stair_len := Vector2(run * steps, rise * steps).length()
	var stair_angle := atan2(rise * steps, run * steps)
	var collider := StaticBody3D.new()
	collider.name = "StairCollision"
	collider.position = Vector3(0, rise * steps * 0.5 - 0.05, -run * steps * 0.5)
	collider.rotation = Vector3(stair_angle, 0, 0)
	var cshape := CollisionShape3D.new()
	var cbox := BoxShape3D.new()
	cbox.size = Vector3(3.0, 0.1, stair_len)
	cshape.shape = cbox
	collider.add_child(cshape)
	stairs.add_child(collider)
	# Landing at the top of the stairs.
	add_box(stairs, "Landing", Vector3(0, rise * steps * 0.5, -run * steps - 2.0), Vector3(3.0, rise * steps, 4.0), "testyard")

	# Low overhang (2.4 m clearance) — walk under it in third person and the
	# camera should pull in instead of clipping through the roof.
	add_box(yard, "Overhang_Roof", Vector3(36.0, 2.4 + 0.25, 14.0), Vector3(8.0, 0.5, 10.0), "testyard_alt")
	for px in [-3.6, 3.6]:
		for pz in [-4.6, 4.6]:
			add_box(yard, "Overhang_Post", Vector3(36.0 + px, 1.2, 14.0 + pz), Vector3(0.4, 2.4, 0.4), "testyard")

	# A row of pillars to weave through (tests camera collision from the side).
	for i in 6:
		add_box(yard, "Pillar", Vector3(30.0 + (i % 2) * 2.5, 2.0, 30.0 + i * 2.5), Vector3(0.8, 4.0, 0.8), "danger")

	# A long wall to run alongside (tests camera with a wall on one side).
	add_box(yard, "Wall", Vector3(42.0, 2.0, 34.0), Vector3(0.5, 4.0, 18.0), "testyard")


## Builds a solid ramp that rises toward -Z, starting at `base` (its low edge).
func _add_ramp(parent: Node3D, ramp_name: String, base: Vector3, angle_deg: float, length: float, width: float, style: String) -> void:
	var a := deg_to_rad(angle_deg)
	var thickness := 0.5
	# Centre of the tilted box such that its low top edge touches the ground.
	var cy := (length * 0.5) * sin(a) - (thickness * 0.5) * cos(a)
	var cz := base.z - (length * 0.5) * cos(a) - (thickness * 0.5) * sin(a)
	add_box(parent, ramp_name, Vector3(base.x, cy, cz), Vector3(width, thickness, length), style, Vector3(a, 0, 0))
	# A platform at the top so the player has somewhere to stand.
	var top_y := length * sin(a)
	var top_z := base.z - length * cos(a)
	add_box(parent, ramp_name + "_Top", Vector3(base.x, top_y * 0.5, top_z - 1.5), Vector3(width, top_y, 3.0), style)


# -------------------------------------------------------------------------
# Boundaries
# -------------------------------------------------------------------------

func _build_world_bounds(root: Node3D) -> void:
	var bounds := Node3D.new()
	bounds.name = "WorldBounds"
	root.add_child(bounds)
	var e := half_extent
	var h := 30.0
	# Invisible walls around the playable area.
	for s in [-1.0, 1.0]:
		add_box(bounds, "BoundX", Vector3(s * (e + 0.5), h * 0.5, 0), Vector3(1.0, h, e * 2.0), "ground", Vector3.ZERO, true, false)
		add_box(bounds, "BoundZ", Vector3(0, h * 0.5, s * (e + 0.5)), Vector3(e * 2.0, h, 1.0), "ground", Vector3.ZERO, true, false)


# -------------------------------------------------------------------------
# Box helper — the one function everything above is built from
# -------------------------------------------------------------------------

## Adds a box. With `collide` it becomes a StaticBody3D the player can stand
## on; without it, it is a purely visual MeshInstance3D.
func add_box(parent: Node3D, box_name: String, pos: Vector3, size: Vector3, style: String,
		rot: Vector3 = Vector3.ZERO, collide: bool = true, visible_mesh: bool = true) -> Node3D:
	var node: Node3D
	if collide:
		var body := StaticBody3D.new()
		body.collision_layer = 1  # "world"
		body.collision_mask = 0   # static things don't need to detect anything
		var shape_node := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = size
		shape_node.shape = shape
		body.add_child(shape_node)
		node = body
	else:
		node = Node3D.new()
	node.name = box_name
	node.position = pos
	node.rotation = rot

	if visible_mesh:
		var mi := MeshInstance3D.new()
		mi.name = "Mesh"
		var mesh := BoxMesh.new()
		mesh.size = size
		mi.mesh = mesh
		mi.material_override = _get_material(style)
		# Thin decals (road paint, sidewalks) don't need to cast shadows.
		if size.y < 0.1:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.add_child(mi)

	parent.add_child(node)
	return node


## One shared material per style keeps draw-call state changes low.
func _get_material(style: String) -> Material:
	if _materials.has(style):
		return _materials[style]
	var colors: Array = PALETTE.get(style, PALETTE["ground"])
	var mat := ShaderMaterial.new()
	mat.shader = GRID_SHADER
	mat.set_shader_parameter("base_color", colors[0])
	mat.set_shader_parameter("line_color", colors[1])
	mat.set_shader_parameter("show_grid", colors[0] != colors[1])
	_materials[style] = mat
	return mat
