# To Be Done

## UI verification
- [ ] Main window fits the screen on first open (1366x768, 1920x1080, 125% / 150% DPI):
      nothing clipped, all buttons reachable (Settings cog, Install, Cancel,
      Check for updates, Update installer, Open game folder).
- [ ] Settings dialog fits as well: engine rows, folder hints, Save/Cancel visible
      without scrolling.
- [ ] Verify the "Creates: ..." hint below the install-folder field:
      - updates when custom unezQuake / FTE folders are set in Settings
      - shows only the remaining engine when one is unticked
      - correct in mods-only mode
      - handles long paths, trailing spaces and quotes
      - refreshes immediately after Settings are saved.

## Check for updates status
- [ ] Add an at-a-glance summary in the results dialog, for example:
      - "Everything is up to date"
      - "All mods are up to date"
      - "unezQuake up to date - FTE update available (1.0 -> 1.1)"
      - "2 mods up to date, 1 update available"
- [ ] Build it from the existing per-component statuses (no extra network calls);
      keep the per-row list as the detail view.
- [ ] Confirm wording for non-OK states: not installed, check failed,
      no build for this platform, other platform.
- [ ] Clarify "launcher" before implementing (engines unezQuake/FTE vs the
      installer itself vs game shortcuts); the installer currently writes no
      shortcuts.
