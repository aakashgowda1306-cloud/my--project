# Milestone M2 — First Drivable Vehicle (plan)

**Status:** planned, not started. Begin only after you have confirmed M1 on your PC.

## Objective
Walk up to an original car, press **E** to get in, drive it around Founders Cross
with a chase camera, press **E** to get out again. Driving should feel weighty
and controllable on a keyboard.

## Scope (in)
1. **Interaction system** (small and reusable): an `Interactable` component +
   a ray/area on the player that finds the nearest interactable and shows a
   prompt ("E — Enter vehicle"). Vehicles are the first user; doors, shops and
   NPCs will reuse it later.
2. **First car: "Aster Civic Line"**, an original compact sedan (fictional brand
   *Aster Motors*). Greybox body built from boxes first, Blender model later.
3. **Driving physics** using Godot's built-in `VehicleBody3D` + 4 `VehicleWheel3D`:
   engine force curve, brakes, handbrake, speed-sensitive steering,
   suspension, anti-roll, downforce at speed. Tuning values in a
   `VehicleData` Resource (`data/vehicles/aster_civic_line.tres`) so future cars
   are data, not code.
4. **Enter / exit**: player hidden and `input_enabled = false` while driving;
   exits to the driver-side door (or the other side if blocked).
5. **Vehicle camera**: chase camera with look-behind and mouse orbit that
   recentres, plus a bonnet/first-person view on **V** (re-using the CameraRig
   blending idea).
6. **HUD**: speedometer (km/h), gear (D/R/N), interaction prompt.
7. **Tests** added to `tests/`: enter/exit, accelerates to X km/h in Y s, brakes to
   stop within Z m, steering turns the car, car doesn't flip on a 30° ramp at
   moderate speed, player is restored correctly on exit.

## Scope (out, later milestones)
Damage, customisation/paint, upgrades, garages and ownership persistence,
other vehicle classes (SUV, sports, motorbike, truck), traffic AI, audio
beyond a simple engine loop.

## Physics decision to measure first
Before tuning, run the same car on **Godot Physics** vs **Jolt**
(Project Settings → Physics → 3D → Physics Engine). Compare stability on the
Test Yard ramps, tunnelling at high speed, and physics time in the Profiler.
Record the result in DEVLOG and pick one for the rest of the project.

## Files expected
```
scripts/systems/interactable.gd
scripts/player/player_interactor.gd
scripts/vehicles/vehicle_data.gd          (Resource)
scripts/vehicles/vehicle_controller.gd
scripts/vehicles/vehicle_camera.gd
scenes/vehicles/aster_civic_line.tscn
data/vehicles/aster_civic_line.tres
UI/hud/vehicle_hud.tscn + .gd
tests/test_runner.gd                      (extended)
```

## Acceptance checklist (to be verified by you on Windows)
- [ ] "E — Enter" prompt appears within ~2 m of the car door.
- [ ] Driving with W/S/A/D, Space handbrake, feels controllable at 30–80 km/h.
- [ ] Car climbs the 15° ramp; doesn't flip on the 30° ramp at ≤40 km/h.
- [ ] Camera never clips into buildings while driving.
- [ ] E exits; player stands beside the car, walking works again.
- [ ] All automated tests pass (old + new).
- [ ] Frame rate on your PC is similar to M1 (note it in DEVLOG).
