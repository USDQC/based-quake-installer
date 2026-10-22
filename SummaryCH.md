# SummaryCH - Based Quake Installer

**Author:** Chuma
**Assisted by:** DeepSeek 4.1

## Context

- Repository: `USDQC/based-quake-installer` (GPLv3).
- Base: `main` @ `f4d92f4` (`Release v1.6.9`).
- Working branch: `CH-updates`, which merges the two feature branches
  (`feat/settings` and `feat/selective-updates`) so everything ships together.
- Test build: `dist\BQICH.exe` (PyInstaller one-file, windowed; local artifact,
  gitignored).

## What was delivered

### 1. Selective updates ("Check for updates")

Before: `Check for updates` showed a read-only list and a single button that
installed every outdated component.

Now:
- One checkbox per component (unezQuake, FTE, each mod/pack).
- `Select all` / `Deselect all`.
- `Engine only` = unezQuake + FTE; `Mods only` = mods + packs.
- `Update selected (N)` applies only the checked subset; disabled at 0.
- Default selection: `update available` only. `not installed` stays unchecked
  unless the user explicitly selects it (Select all/presets).
- Non-installable rows are disabled: `up to date`, `check failed`,
  `other platform`, `no build for this platform`.
- Re-running Check replaces the open dialog instead of stacking windows;
  Escape/Close work.
- Backend: `apply_updates()` already accepted an item subset, so no change to the
  download/install flow was needed.
- Pure selection helpers (`is_selectable`, `select_components`) are unit tested.

### 2. Settings window (cog) and engine targets

Before: theme picker in the header; no way to choose engines or their folders.

Now:
- Gear button (generated light/dark PNGs, tooltip, `Ctrl+,`) opens **Settings**.
- **Engines (full install)**: tick unezQuake and/or FTE, each with an optional
  target folder (blank = `<install root>/unezQuake` or `<root>/FTE`).
- Skipped engines are not downloaded, not given `pak0.pak`, configs or mods, and
  do not appear in update checks. Their existing files are left untouched.
- Custom targets are reused if present; user cfgs remain protected.
- **Remember install directory and client folders** (default ON): off means folder
  values are not loaded/saved next launch; name/look/binds are still remembered.
- Theme picker and the installer self-check checkbox moved into Settings.
- Settings keys are backward compatible with old `settings.json` files.
- Plumbing: `Options` gained `install_unez`/`install_fte` plus
  `unez_target`/`fte_target`; `run_install`, `install_clients`, configs, mods,
  shareware data, FTE setup and the updater honor the selection.
- Settings are stored per user (pre-existing location, not changed by this work):
  - Windows: `%APPDATA%\BasedQuakeInstaller\settings.json`
  - Linux: `$XDG_CONFIG_HOME/based-quake-installer/settings.json`
  - Keys include `root`, `install_unez`, `install_fte`, `unez_install_path`,
    `fte_install_path`, `remember_dirs`, plus the pre-existing name/binds/theme.

### 3. Screen fit (main window and Settings)

- Main window content is scrollable (always-visible scrollbar, mouse wheel);
  window min size is computed from the screen and margins keep it clear of the
  title bar/taskbar.
- Settings sections scroll, while `Save`/`Cancel` stay pinned in a fixed footer.
- Hint labels wrap instead of forcing the window wider.
- Measured at Tk scaling 1.0 / 1.333 / 1.5 / 2.0 on a 1536x864 desktop: the window
  opens within margins and the content stays reachable.

### 4. Install-folder hint

- Wording changed from the misleading `Creates: ...` to `Installs to: ...`.
- Each path is marked `(existing)` or `(new)`.
- Mods-only mode shows `Mods go into: ... (existing)/(new)`.
- Only selected engines are shown; blank target falls back to the install root.
- Handles quotes, leading/trailing spaces, `~`, and long paths (wrapped).
- Pure `paths_hint()` helper with injected existence check for deterministic tests.

### 5. Check-for-updates summary

- Headline plus two muted group lines:
  - `Engines: unezQuake and FTE are up to date.`
  - `Engines: unezQuake update available; FTE up to date.`
  - `Mods: all up to date (11).`
  - `Mods: 2 updates available, 1 not installed, 1 check failed.`
  - `No updates available, but some checks need attention.` when only errors,
    other-platform or no-build rows exist.
- Missing items count as available installs/updates; a failed check never claims
  "up to date".
- Built entirely from data already returned by the update check (no extra network
  calls); per-row detail and selection stay unchanged.
- "Launcher" from the original request was resolved as the engines
  (unezQuake/FTE); the installer self-update remains its own check.

### 6. Docs and tests

- `worklogCH.md`: decisions, progress and verification.
- `ToBeDone.md`: items checked off (screenshots + CLI flags remain as follow-ups).
- Manual: Settings section, engine targets, remembered settings, install steps,
  folder hint wording, update summary.
- README: Settings/engine feature line.
- Tests added/extended:
  - `tests/test_settings.py` (new keys, old-file compatibility).
  - `tests/test_install_engines.py` (unez-only install skips FTE; custom targets).
  - `tests/test_paths_hint.py` (full/mods-only, existing/new, quotes/spaces).
  - `tests/test_updates.py` (selection matrix, subset apply, engine filtering,
    summary wording/pluralisation).

## How it behaves (quick reference)

- Full install: selected engines only; blank folder = under the install root;
  existing folder = reused; new folder = created by the installer.
- Mods-only mode: unchanged; uses the main-window unezQuake/FTE folders and
  ignores the Settings engine selection.
- Check for updates: enabled engines only; choose rows explicitly; only the
  selected rows are downloaded and recorded in `based-quake-manifest.json`.
- Remember off: next launch starts from defaults for folders but keeps
  name/look/binds and engine selection.

## Verification

- `python -m pytest -q tests -p no:cacheprovider` -> **198 passed, 6 skipped**.
- Tk smoke tests (throwaway, temp APPDATA): Settings save/reload, engine/path
  propagation, dark theme, selectable update dialog, summary lines.
- Screen-fit measurement at four Tk scaling values (see above).
- `python installer_cli.py --self-test` -> `ok: true`.
- Rebuilt `dist\BQICH.exe` and ran `--self-test` -> exit 0, `ok: true`.
  Latest build: 11,361,937 bytes,
  SHA256 `EA33520B30F8E8336BA524A95312B20F49E3EE7C4A0FE2CF7FA6D125EDD75126`.

## Branch history (CH-updates)

- `154ece2` Merge `feat/selective-updates`
- `de62dfa` Merge `feat/settings`
- `a78f65d` UI: fit screen, folder hint and update summary
- `a292c2f` UI: say `Installs to` and mark existing/new folders

The two feature branches are kept until the combined PR is merged; no PR has
been submitted yet.

## Not included / follow-ups

- Manual screenshots still show the old header/update dialog; regenerate.
- CLI flags for engine selection (`--update-unez/--update-fte/--update-mods`,
  engine install flags) are not implemented.
- Installer self-update remains check-only; it never installs automatically.
- A true mixed mode ("use my existing unezQuake for mods but install FTE") is
  still a mods-only-mode/manual-folder job; Settings installs the engine into the
  chosen folder.
- Unused `head=` parameter in `updater.check_updates` can be cleaned up.
