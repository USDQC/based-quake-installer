# To Be Done

Everything below was implemented and verified on `CH-updates`.

## UI verification
- [x] Main window fits the screen on first open (1366x768, 1920x1080, 125% / 150% DPI):
      nothing clipped, all buttons reachable (Settings cog, Install, Cancel,
      Check for updates, Update installer, Open game folder).
      - Main window content now scrolls when DPI scaling makes it taller than the
        screen; margins keep the title bar/taskbar clear.
      - Measured at Tk scaling 1.0 / 1.333 / 1.5 / 2.0 on a 1536x864 desktop:
        window opens at 960x680 (or the screen limit) and the content is reachable.
- [x] Settings dialog fits as well: engine rows, folder hints, Save/Cancel visible
      without scrolling.
      - The four sections scroll inside the dialog; Save/Cancel stay pinned in the
        footer at any window/screen height.
- [x] Verify the "Installs to: ..." hint below the install-folder field:
      - updates when custom unezQuake / FTE folders are set in Settings
      - shows only the remaining engine when one is unticked
      - marks each folder `(existing)` or `(new)`
      - correct in mods-only mode ("Mods go into: ...")
      - handles long paths (wrapped), trailing spaces and quotes, `~`
      - refreshes immediately after Settings are saved
      - pure `paths_hint()` helper covered in `tests/test_paths_hint.py`.

## Check for updates status
- [x] Add an at-a-glance summary in the results dialog:
      - "Everything is up to date."
      - "Engines: unezQuake and FTE are up to date."
      - "Engines: unezQuake update available; FTE up to date."
      - "Mods: all up to date (11)."
      - "Mods: 2 updates available, 1 not installed, 1 check failed."
      - "No updates available, but some checks need attention." when only
        errors/other-platform/no-build rows are present.
- [x] Build it from the existing per-component statuses (no extra network calls);
      per-row detail and selection are unchanged.
      - `updater.check_summary()` + tests in `tests/test_updates.py`.
- [x] Confirm wording for non-OK states: not installed, check failed,
      no build for this platform, other platform.
- [x] "Launcher" resolved as the engines (unezQuake/FTE); the installer
      self-update remains a separate check.

## Follow-ups
- [ ] Regenerate manual screenshots (the result window now has a summary; the
      header no longer carries the theme picker).
- [ ] Optional: CLI flags for engine selection.
