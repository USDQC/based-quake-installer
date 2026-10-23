# CLI update - CH

Date: 2026-10-23 09:12 (-04:00)
Branch: `CH-updates`
Status: CLI kept for correctness/headless use; full GUI parity is still optional.

## Why

The GUI gained engine selection, custom engine folders, manifest folder memory
and turned-off-engine notes. The CLI still called `check_updates()` without the
`Options` object and could traceback on update errors. This pass fixes the
correctness gaps only; it does not add new CLI features.

## Fixes

### 1. `--check-updates` follows the install record

`installer_cli.py` used:

```python
items = updater.check_updates(a.root, opts.platform)
```

It now passes the same options used by the install/update path:

```python
items = updater.check_updates(root, opts.platform, opts=opts)
```

Effect:

- `--check-updates` uses the engine folders recorded in
  `based-quake-manifest.json`, including custom folders.
- `--update` receives accurate items for custom-folder installs instead of
  checking the default `root/unezQuake` and `root/FTE` paths.

### 2. `--update` handles install errors cleanly

`updater.apply_updates()` can raise `InstallError` (for example when folder
rules reject a nested layout). The CLI update branch now catches it:

```python
try:
    up, failed = updater.apply_updates(opts, items, Reporter())
except InstallError as exc:
    print("ERROR: %s" % exc, file=sys.stderr)
    return 1
```

No Python traceback; exit code 1 and a normal `ERROR:` line.

### 3. `--root` must be a full path

The CLI now cleans and validates the root before building `Options`:

```python
root = folders.clean(a.root)
if not folders.is_full_path(root):
    ap.error("--root must be a full path, e.g. C:\\Games")
```

- Relative paths such as `--root Games` are rejected with argparse exit code 2.
- `~` expansion still works (`--root ~/Games`).
- The `--root` help text now says it must be a full path.

### 4. CLI tests

Added `tests/test_cli.py`:

- `--check-updates` passes `opts` to `updater.check_updates()`
- `--update` passes the same `opts` and handles `InstallError` with exit 1
- a relative `--root` is rejected with exit code 2

### 5. Manual

Chapter 9 now documents:

- `--root` must be a full path.
- `--check-updates` and `--update` follow the folders recorded in the install
  manifest, including custom engine folders.

## Not changed

- No `--no-unez` / `--no-fte` engine switches.
- No `--unez-dir` / `--fte-dir` custom folder flags.
- No `--existing` mode with arbitrary `--unez-path` / `--fte-path` folders.
- No selective update flags (`--update-unez`, etc.).
- The CLI still does not read `settings.json`; it uses its arguments and the
  install manifest.

## Verification

- `python -m pytest -q tests -p no:cacheprovider` -> 232 passed, 7 skipped.
- `python installer_cli.py --self-test` -> ok.
- `python installer_cli.py --version` -> `Based Quake Installer 1.7.0`.
- `dist\BQICH.exe` is unaffected (it is the GUI build); no BQICH rebuild needed
  for this pass. Run `build_exe.bat` if a frozen `BasedQuakeInstaller-cli.exe`
  is wanted.
