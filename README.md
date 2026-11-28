# AFTERLIGHT

*Every decision leaves a mark. Every action changes the city.*

An original open-world 3D action crime drama set in Nova City, Aether State, 2042.
Built with **Godot 4.7** (GDScript) and **Blender**.

**Current milestone:** Phase 1 (Foundation) ✅: a playable on-foot prototype in
a greybox Nova City district with third/first-person camera.

## Quick start
1. Install Godot 4.7.2 (Standard, not .NET) and Git. Full steps: [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md).
2. Godot Project Manager → **Import** → select `project.godot` → **Import & Edit**.
3. Press **F5**.

Controls: **WASD** move · **Mouse** look · **Shift** sprint · **Ctrl** walk ·
**Space** jump · **V** first/third person · **Wheel** zoom · **F3** debug · **Esc** free mouse.

## Run the tests
```powershell
& "C:\Godot\Godot_v4.7.2-stable_win64_console.exe" --headless --path . --import
& "C:\Godot\Godot_v4.7.2-stable_win64_console.exe" --headless --path . --fixed-fps 60 -s res://tests/test_runner.gd
```
Expected last line: `===== 51 passed, 0 failed =====`.

## Documentation
| File | Contents |
|---|---|
| [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) | Installing Git, Godot, Blender; running the game and tests |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Scene trees, scripts, layers, design decisions |
| [docs/DEVLOG.md](docs/DEVLOG.md) | Development log |
| [docs/KNOWN_BUGS.md](docs/KNOWN_BUGS.md) | Known bugs and limitations |
| [docs/FEATURE_TRACKER.md](docs/FEATURE_TRACKER.md) | Feature completion per phase |
| [docs/milestones/M2_FIRST_VEHICLE.md](docs/milestones/M2_FIRST_VEHICLE.md) | Plan for the next milestone |

## Originality
All names, places, characters, vehicles and art in AFTERLIGHT are original.
No assets or content from other games are used.
