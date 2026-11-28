# AFTERLIGHT — Known Bugs & Limitations

Status: 🔴 open bug · 🟡 limitation / by design for now · 🟢 fixed

| # | Status | Area | Description | Workaround / plan |
|---|---|---|---|---|
| 1 | 🟡 | Player | No character animations yet; the player is a capsule with a small walking bob. | Replace with a rigged Blender character + AnimationTree in a later milestone. |
| 2 | 🟡 | Engine (4.3 only) | On **Godot 4.3 headless** runs, ~180 `mesh_get_surface_count: Parameter "m" is null` errors print *at shutdown*, after the game/tests have finished. Comes from 4.3's dummy renderer freeing runtime-created meshes. Does not happen on 4.7.2. Does not affect results. | Use Godot 4.7.2. |
| 3 | 🟡 | Camera | Mouse sensitivity is fixed in the Inspector (`CameraRig > Mouse Sensitivity`); no in-game settings menu yet. | Settings menu planned with graphics settings (Phase 8). |
| 4 | 🟡 | Camera | No gamepad look support yet (keyboard + mouse only). `CameraRig.add_look_input()` is ready for it. | Add gamepad bindings when needed. |
| 5 | 🟡 | World | Stairs use an invisible ramp for collision; there is no general "step up" logic, so the player can't walk up a sharp 20 cm kerb. Sidewalks are therefore flush with the road in this blockout. | Revisit when real kerbs/props arrive (step-up via `test_move`, or ramped kerb colliders). |
| 6 | 🟡 | World | District geometry is generated at load (not saved in the .tscn), so individual buildings can't be hand-moved in the editor. | Intentional for greyboxing; real districts will be hand-built scenes from Blender assets. |
| 7 | 🟡 | Testing | Visual checks here were done with the OpenGL (Compatibility) renderer and software rendering; Forward+ on a real GPU may look slightly different (softer shadows, different exposure). | Check visuals on your PC; report anything odd. |
