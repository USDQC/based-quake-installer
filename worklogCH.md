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

## 2026-10-22 - CH-updates (single PR branch)

- `CH-updates` combines `feat/settings` + `feat/selective-updates` with merge
  commits; this is the branch to review and the one BQICH is built from.
- Old feature branches and local `test/settings+updates` stay until the PR is
  merged, then can be deleted.

## 2026-10-22 - ToBeDone pass (fit, hint, update summary)

### Decisions
- "Launcher" in the list = the engines (unezQuake/FTE); the installer self-update
  stays separate.
- Summary reads as a headline plus two group lines (Engines, Mods).
- Screen fit handled adaptively: main window scrolls; Settings content scrolls
  with a fixed Save/Cancel footer.

### Implementation
- `gui.py`:
  - main content is inside a canvas + always-visible scrollbar (wheel support,
    Text/Combobox keep their own wheel); dynamic `minsize` and
    `center_window(..., margin_x=24, margin_y=72)` keep it on-screen.
  - Settings sections live in `_scrollable()`; footer outside so it never clips.
  - new pure `paths_hint()`; hint moved below the mode frames so it works in both
    modes and wraps on resize. Wording is `Installs to:` (not "Creates") and each
    folder is marked `(existing)` or `(new)`; mods-only shows `Mods go into:` with
    the same markers.
  - Check for updates shows `updater.check_summary()` headline + Engines/Mods lines.
- `updater.py`: `check_summary()` (missing counts as available, errors/platform
  never claim "up to date").
- Tests: `tests/test_paths_hint.py`, summary cases in `tests/test_updates.py`.
- Docs: manual update chapter mentions the summary; `ToBeDone.md` checked off.

### Verification
- `python -m pytest -q tests -p no:cacheprovider` -> 198 passed, 6 skipped.
- Tk smokes pass (Settings/cog, selectable update dialog, summary lines).
- Fit measurement at Tk scaling 1.0/1.333/1.5/2.0 on a 1536x864 desktop: main
  window opens within margins and content scrolls; Settings fits and scrolls.
- Rebuilt `dist\BQICH.exe` and `--self-test` exit 0.

### Documentation
- `SummaryCH.md`: full hand-off summary (author Chuma, assisted by DeepSeek 4.1).
- Folder hint wording: `Installs to: ... (existing)/(new)`; mods-only
  `Mods go into: ...`; tests updated.

## 2026-10-22 22:44 - Sisson's and Moose Feedback

Source: Sisson (Grok-based Discord review) passed on by Moose.
Branch: `CH-updates` only. These five notes are the scope of PR 1; no merge or
cherry-pick from any other branch.

### Specific notes
- [x] **Dark theme black band** - the new scrolling area doesn't pick up Dark
      colours, which leaves a black strip at the bottom.
- [x] **Folder safety** - unezQuake and FTE could use the same folder or one
      inside the other, which would mix their files. Chuma decision: a shared
      folder is allowed with a warning, an install root / sibling folder is
      allowed, and nesting is still rejected.
- [x] **Updates remember where clients are** - with custom folders and
      "remember folders" off, update checks could lose track and reinstall into
      the default folders. The install record must save the real folders.
- [x] **Turned-off clients** - an installed client that is unticked should show
      a note in Check for updates instead of just vanishing.
- [x] **Cleanup** - clearer wording, split the big Settings function. Chuma
      keeps the work-log/notes files in the repo (deviation from the review).

### Implementation
- `folders.py`: one full-path check plus `check_existing_folders()` /
  `check_engine_folders()`. Equal/shared folders are allowed with a warning;
  an engine folder may equal the install root or be a sibling; nesting and an
  engine folder above the install root are still rejected. `installed` folders
  (from the manifest) are used for turned-off engines.
- Enforced from Settings save, `_collect`, `_collect_existing`,
  `run_install`, `run_existing` and `apply_updates`; GUI asks before a shared
  folder, backend logs the warning.
- `manifest.py`: `record_engines()` / `engine_dirs()` / `engine_folders()`;
  `installer.Options` gained `use_manifest_dirs()`, `check_folders()` and
  `folder_warning()`.
- Full install and in-root mods-only save `engine_dirs`; Check for updates and
  Apply updates follow the recorded folders (old manifests fall back).
- `updater.turned_off_notes()`; GUI appends the note to the update summary and
  log.
- Dark theme: main scroll canvas is themed and fills the window; `_scrollable()`
  canvases get the current theme background when created.
- Settings moved to `quake_installer/settings_dialog.py`; hidden import added to
  `build_exe.bat`; wording cleaned up. Notes and CH markers kept.
- Tests: `tests/test_folders.py`; `tests/test_paths_hint.py` wording.

### Progress
- [x] Folder rules added and enforced (Settings, Install, mods-only, updates)
- [x] Engine folders recorded in the manifest and used by update checks
- [x] Note shown for installed-but-turned-off engines
- [x] Dark theme canvas fill/recolor fixed (main window and dialogs)
- [x] Settings moved to `settings_dialog.py`; wording cleaned up
- [x] Tests pass; CLI/GUI self-tests pass

### Verification
- `python -m pytest -q tests -p no:cacheprovider` -> 228 passed, 7 skipped.
- `python installer_cli.py --self-test` -> ok.
- `python installer_gui.py --self-test <report>` -> ok.
- Throwaway Tk smoke (temp APPDATA): Dark main canvas and Settings canvas both
  `#1c1c1c`, matching the `TFrame` background.
- `installer.Options(root=C:\nQuake, unez=C:\nQuake, fte=C:\fteqw)` passes
  `check_folders()` with no shared-folder warning.
- Rebuilt `dist\BQICH.exe` (11,370,809 bytes); frozen `--self-test` exit 0 and
  `folders` / `settings_dialog` are bundled.

## 2026-10-23 08:11 - Action bar layout

- Action bar is now a 3-column layout: left install actions, centre folder
  button, right installer-update group.
- Left: `Install` / `Update configs only` / `Check for updates` / `Cancel`.
  Centre: `Open game folder` (centred in the free space). Right: self-update
  notice + `Update installer`.
- Tk smoke: folder centre at x=909, midpoint between the groups x=914 (within
  6px); no fixed padding hack.
- Rebuilt `dist\BQICH.exe` (11,371,144 bytes), frozen self-test exit 0;
  pytest 228 passed, 7 skipped.
- FTE config wording change deferred (blue-line question).

## 2026-10-23 08:27 - Version 1.7.0

- Bumped `quake_installer/__init__.py` from `1.6.9` to `1.7.0`; the GUI header,
  CLI `--version` and self-test report now show 1.7.0.
- Manual still says 1.6.9 (not changed in this pass).
- pytest 228 passed, 7 skipped.
- Rebuilt `dist\BQICH.exe` (11,371,085 bytes); frozen self-test version 1.7.0,
  exit 0.

## 2026-10-23 08:41 - FTE config wording

- `existing.py`: role + short reason. Examples:
  `FTE configs: C:\fteqw  (install folder; no FTE home folder found)`,
  `(home folder; found automatically)`, `(install folder; disabled by default.fmf)`,
  `(home folder; forced by default.fmf)`, `needs a choice`.
- `gui.py`: the "your choice" line now names the folder role; the prompt reads
  "Where does FTE save its configs?"; "FTE folder not found yet." -> "FTE folder
  not found."; log says "FTE config folder".
- Added `test_describe_wording` (no cfg required; folder layout decides).
- pytest 229 passed, 7 skipped.
- Rebuilt BQICH cleanly (11,370,934 bytes, 08:42); frozen self-test version
  1.7.0, exit 0. Removed the temporary `dist\BQICH-old.exe` after closing the
  old instance.

## 2026-10-23 09:12 - CLI correctness

See `CLIupdateCH.md` for the full write-up.

- `installer_cli.py`: `--check-updates` now passes `opts` to
  `updater.check_updates()` so it follows manifest-recorded folders;
  `--update` catches `InstallError` and exits 1 cleanly; `--root` must be a
  full path; help text updated.
- `tests/test_cli.py`: opts forwarding, update error handling, relative-root
  rejection.
- Manual chapter 9 notes the full-path rule and manifest folder behavior.
- pytest 232 passed, 7 skipped; CLI `--self-test` and `--version` ok.
- No BQICH rebuild needed (GUI build unaffected).
