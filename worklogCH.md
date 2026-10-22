# Worklog - CH

Author : Chuma

assisted with Deepseek 4.1 Flash.

branch : feat/selective-updates

One log per work stream. Keep it short, dated by task, and update it whenever a
decision or note changes.

Conventions
- Code comments for non-obvious / heavily changed blocks: `# CH - <short reason>`
  (one line, only where it helps; never line-by-line narration).
- No pushes to `main`: work on `feat/<name>`, push the branch, open a PR.

## 2026-10-22 - Selective updates (PR)

Branch: `feat/selective-updates` (from `main` @ f4d92f4)

### Problem
`Check for updates` lists clients and mods, but the only action is a single
`Update N` that installs every outdated/missing item. There is no way to update
only unezQuake, only FTE, or only mods, and no way to pick a subset.

### Decisions (agreed)
- Design: selection inside the existing "Check for updates" dialog, not a new
  "Update unezQuake" toolbar button (keeps one code path, shows status first).
- Checkboxes per component, plus `Select all` / `Deselect all`.
- Presets: `Engine only` = unezQuake + FTE; `Mods only` = mods + packs.
- `not installed` rows start unchecked (Select all/presets may still include
  them; default never installs something unrequested).
- Scope: GUI only. CLI flags deferred.
- Non-selectable rows stay disabled: `up to date`, `check failed`,
  `other platform`, `no build for this platform`.
- Out of scope: repair/force re-download, CLI parity, dead `head=` param,
  platform-mismatch messaging cleanup.

### Plan
1. `quake_installer/updater.py`: pure selection helpers (`is_selectable`,
   `select_components`) - no Tk, unit-testable.
2. `quake_installer/gui.py`: rewrite `_show_updates` with scrollable checkbox
   rows, preset buttons and `Update selected (N)`; keep `_start_update` /
   `apply_updates` unchanged.
3. `tests/test_updates.py`: selection matrix + `apply_updates` subset test.
4. Verify: `python -m pytest -q tests -p no:cacheprovider`, manual GUI pass.
5. Commit, push branch only, PR to `main`.

### Files touched
- `worklogCH.md` (this file)
- `quake_installer/updater.py`
- `quake_installer/gui.py`
- `tests/test_updates.py`

### Progress
- [x] Branch created
- [x] Worklog created
- [x] updater helpers (`is_selectable`, `select_components`)
- [x] dialog rewrite (checkbox rows, presets, Update selected)
- [x] tests (selection matrix + apply subset)
- [x] pytest: `176 passed, 6 skipped`
- [x] GUI smoke (defaults, Select/Deselect all, presets, subset apply, all-disabled, dark)
- [x] commit / push / PR

### Implementation notes
- `Check for updates` dialog is now a scrollable checkbox list; non-installable
  rows (`up to date`, `check failed`, `other platform`, `no build`) are disabled.
- Default checks `update available` only. `Select all`, `Engine only` and
  `Mods only` include `not installed` rows (explicit user action); `Deselect all`
  clears everything.
- `Engine only` = unezQuake + FTE; `Mods only` = mods + packs.
- Buttons show `Update selected (N)` and disable at 0; empty groups disable their
  preset. Re-running Check replaces the open dialog instead of stacking.
- `apply_updates()`, manifest format and the CLI are unchanged.

### Verification
- `python -m pytest -q tests -p no:cacheprovider` -> 176 passed, 6 skipped.
- Throwaway Tk smoke test (temp dir, not committed): dialog opens in classic and
  dark themes, defaults are correct, presets/select-all behave, the checked
  subset reaches `_start_update`, all-disabled case disables presets + Update.

### Follow-ups
- CLI parity (`--update-unez/--update-fte/--update-mods`).
- Repair/force re-download for `up to date` rows.
- Drop the unused `head=` parameter in `updater.check_updates`.
- Platform-mismatch messaging cleanup.

## 2026-10-22 - Settings window (PR)

Branch: `feat/settings` (from `main` @ f4d92f4; worklog brought over from `feat/selective-updates`)

### Decisions (agreed)
- Cog button opens a Settings window; theme picker and the installer
  self-check checkbox move inside.
- Engines: per-engine checkboxes plus an optional folder each (blank = under the
  install root). unezQuake and FTE on by default.
- `Remember install directory and client folders` on by default; off = folder
  fields start from defaults each launch (name/look/binds still remembered).
- Cog is a generated gear PNG (light/dark variants) bundled with the assets.
- Separate branch/PR from the selective-updates work; pushes stay on the branch.

### Implementation
- `settings.py`: new keys `remember_dirs`, `install_unez`, `install_fte`,
  `unez_install_path`, `fte_install_path` (old settings files keep working).
- `installer.py`: `Options` gained `install_unez/install_fte` and
  `unez_target/fte_target`; a skipped engine's `*_dir` is `None` so mods,
  pak0 and cfgs never land there. `run_install`, `install_clients`,
  `cfg_targets` and `_configure_fte` follow the selection.
- `updater.py`: Check for updates omits unselected engines and mods that only
  support them; `_mod_present` follows custom folders.
- `gui.py`: gear button + tooltip (Ctrl+,), Settings dialog, live path hint,
  validation (one engine, distinct absolute folders, warning for odd folders),
  remember-dirs behaviour in load/save.
- `manual/render_gear.py` + `quake_installer/assets/icons/` gear PNGs.
- Docs: README feature line, manual Settings section, button table, remembered
  settings note, install steps.

### Progress
- [x] Branch + worklog
- [x] settings keys
- [x] installer/updater engine selection
- [x] Settings dialog + cog
- [x] gear icons
- [x] tests (settings, engine install, update filtering)
- [x] pytest: 179 passed, 6 skipped
- [x] GUI smoke (cog, Settings save, remember off, dark theme)
- [x] commit `bf7e9a7` + push `feat/settings` (PR page opened, not submitted)

### Verification
- `python -m pytest -q tests -p no:cacheprovider` -> 179 passed, 6 skipped.
- Throwaway Tk smoke (temp APPDATA): cog icon loads, Settings saves engine choice,
  path hint drops FTE, remember-off removes folder values from settings.json,
  dark theme reloads the cog icon.

### Follow-ups
- Screenshots in the manual still show the old header (theme picker); regenerate.
- CLI flags for engine selection (not in this PR).
- Mixed "use my existing unezQuake folder for mods but install FTE" remains a
  mods-only-mode job; the Settings folder override installs the engine there.
