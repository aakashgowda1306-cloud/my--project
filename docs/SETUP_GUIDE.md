# AFTERLIGHT — Setup Guide (Windows 11)

This guide takes you from a fresh Windows 11 PC to running AFTERLIGHT and its
automated tests. Follow it top to bottom the first time.

> Tested versions: the project was built and tested with **Godot 4.7.2**
> (current stable) and also passes all tests on **Godot 4.3**. Any Godot 4.3 or
> newer should work; 4.7.2 is recommended.

---

## 1. Install Git for Windows

1. Go to <https://git-scm.com/download/win> and download the 64-bit installer.
2. Run it. The defaults are fine. On the "Adjusting your PATH" page keep
   **"Git from the command line and also from 3rd-party software"**.
3. Open **PowerShell** (Start menu → type `PowerShell`) and check:

   ```powershell
   git --version
   ```

   Expected: something like `git version 2.47.0.windows.1`.

4. Tell Git who you are (only once per PC):

   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

## 2. Get the project

```powershell
cd $HOME\Documents
git clone https://github.com/aakashgowda1306-cloud/my--project.git AFTERLIGHT
cd AFTERLIGHT
git checkout ccr-0731d00c-mcg19z
```

Expected: a folder `Documents\AFTERLIGHT` containing `project.godot`.

> If the branch has been merged into `main` by the time you read this,
> use `git checkout main` instead.

## 3. Install Godot 4.7.2

Godot needs no installer. It is a single program you unzip.

1. Go to <https://godotengine.org/download/windows/>.
2. Download **Godot Engine – Standard** (NOT the ".NET" version; we use GDScript).
   If the page shows a newer 4.x version, that is fine too.
3. Create the folder `C:\Godot` and unzip into it. You get two files:
   * `Godot_v4.7.2-stable_win64.exe` (the editor, which you double-click)
   * `Godot_v4.7.2-stable_win64_console.exe` (the same program, but it shows a
     console window with log output; we use it for tests)
4. Optional: right-click the first `.exe` → **Send to → Desktop (create shortcut)**.

## 4. Open the project in Godot

1. Start `Godot_v4.7.2-stable_win64.exe`.
2. The **Project Manager** opens. Click **Import** (top left).
3. Browse to `Documents\AFTERLIGHT\project.godot` → **Open** → **Import & Edit**.
4. The first time, Godot imports assets for a few seconds.
5. If Godot says the project was made with an older/newer version and asks to
   convert/upgrade: for 4.7.x click **OK**. If you are on 4.3–4.6 you may see a
   warning that the project targets 4.7. It still works; click **Continue**.

**Renderer.** The project uses **Forward+** (best quality). It needs a GPU with
Vulkan support (almost every GPU from the last ~8 years, including Intel UHD
integrated graphics). If the editor shows a black screen or a Vulkan error:
**Project → Project Settings → General → Rendering → Renderer → Rendering Method**
→ choose `gl_compatibility` → restart the editor.

## 5. Run the game

* Press **F5** (or the ▶ "Run Project" button, top right).
* A 1600×900 window opens with the player standing on a sidewalk at the
  *Founders Cross* crossroads in Nova City.

### Controls

| Key | Action |
|-----|--------|
| W A S D | Move (relative to the camera) |
| Mouse | Look around |
| Shift (hold) | Sprint (uses stamina) |
| Ctrl (hold) | Walk slowly |
| Space | Jump |
| V | Switch first-person ↔ third-person |
| Mouse wheel | Zoom the third-person camera |
| F3 | Show/hide the debug panel |
| Esc | Free the mouse (click the window to capture it again) |

To stop the game press **F8** in the editor or close the game window.

## 6. Run the automated tests

The tests start the real game without a window, simulate key presses and check
51 things (movement, sprint, stamina, jumping, camera switching, camera
collision, respawn…).

In PowerShell, inside the project folder:

```powershell
cd $HOME\Documents\AFTERLIGHT
$godot = "C:\Godot\Godot_v4.7.2-stable_win64_console.exe"
& $godot --headless --path . --import
& $godot --headless --path . --fixed-fps 60 -s res://tests/test_runner.gd
echo "Exit code: $LASTEXITCODE"
```

The `--import` line builds Godot's cache (the hidden `.godot` folder) and then
quits. It's only strictly needed on a fresh clone, but running it every time is
harmless.

Expected output (abridged):

```
===== AFTERLIGHT Phase 1 tests (Godot 4.7.2-stable (official)) =====
  PASS  main scene is res://scenes/main/main.tscn
  PASS  input action 'move_forward' is mapped
  ...
  PASS  camera stays below the overhang roof (no clipping)
  PASS  falling out of the world respawns the player at PlayerSpawn
===== 51 passed, 0 failed =====
Exit code: 0
```

Any line starting with `FAIL` means something is broken. The text after it
tells you what was measured.

> If you skip `--import` on a fresh clone you will see
> `Parse Error: Could not find type "PlayerController"`. That's not a bug in the
> game; Godot just hasn't registered the script class names yet. Run the
> `--import` line (or open the project in the editor once) and try again.

## 7. Install and configure Blender (for later milestones)

We don't need Blender until we replace the grey boxes with real art, but set it
up now so it's ready.

1. Download the latest **LTS** version from <https://www.blender.org/download/lts/>
   (Long-Term Support = stable, fewer surprises). Install with defaults.
2. Configure it for Godot (do this once, then **File → Defaults → Save Startup File**):
   * **Scene Properties → Units**: Unit System `Metric`, Unit Scale `1.0`,
     Length `Meters`. *1 Blender unit = 1 metre = 1 Godot unit.*
   * **Edit → Preferences → Interface**: tick *Developer Extras* (shows Python
     tooltips; handy later).
3. Export rules for AFTERLIGHT:
   * Model with the object's **origin at its base** (feet of a character,
     bottom-centre of a building or car) so it sits on the ground in Godot.
   * Apply transforms before export: **Ctrl+A → All Transforms**.
   * Export with **File → Export → glTF 2.0** → format **glTF Binary (.glb)**,
     tick *Apply Modifiers*, keep *+Y Up* ticked.
   * Save `.blend` source files in `blender/` and exported `.glb` files in the
     matching `assets/` folder (e.g. `assets/vehicles/`). Godot auto-imports `.glb`.
   * **Facing direction:** a model that faces the Blender *front* view (−Y)
     will face **+Z** in Godot. AFTERLIGHT's player and vehicles treat **−Z** as
     forward, so rotate imported characters/cars 180° around Y inside their
     scene (we'll do this together when we import the first car).

> I have not installed or tested Blender in this environment. The settings
> above are standard for a Blender → Godot glTF pipeline.

## 8. Daily Git workflow

```powershell
git status                 # what changed?
git add -A                 # stage everything
git commit -m "Describe what you did"
git push                   # upload to GitHub
```

Before any big change, make a checkpoint commit so you can always go back:

```powershell
git log --oneline          # list checkpoints
git checkout <commit-id> -- path\to\file   # restore one file from a checkpoint
```

Never commit the `.godot/` folder (it's in `.gitignore`; Godot rebuilds it).
DO commit the `*.uid` and `*.import` files Godot creates next to your files.
They keep references between scenes stable.
