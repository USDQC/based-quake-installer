"""Headless variant (same engine as the GUI) -- handy for testing or scripting.

Example:
  python installer_cli.py --root "D:\\Games" --name Ranger --preset wasd --look gl
"""

import argparse
import sys

from quake_installer import __version__, cfg
from quake_installer.constants import DEFAULT_ROOT, host_platform
from quake_installer.installer import InstallError, Options, run_install
from quake_installer.mods import load_specs


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Based Quake Installer (no GUI). Installs engines + all mods together.")
    ap.add_argument("--version", action="version", version="Based Quake Installer %s" % __version__)
    ap.add_argument("--self-test", action="store_true",
                    help="check that the program and its bundled tools start, then exit")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--name", default="player")
    ap.add_argument("--preset", choices=("none", "vanilla", "wasd", "modern"), default="vanilla",
                    help="bind defaults (default: vanilla = stock default.cfg). wasd = vanilla + "
                         "WASD movement; modern = wasd + modern weapon keys (it includes WASD). "
                         "none = no binds")
    ap.add_argument("--movement", choices=("vanilla", "wasd"), default=None,
                    help="legacy: combine with --weapons into a bind preset")
    ap.add_argument("--weapons", choices=("vanilla", "modern"), default=None,
                    help="legacy: combine with --movement into a bind preset")
    ap.add_argument("--look", choices=("soft", "gl"), default="soft")
    ap.add_argument("--configs-only", action="store_true",
                    help="only rewrite autoexec.cfg (+ FTE default.fmf) in an existing install")
    ap.add_argument("--mods", default="all",
                    help="comma list of mod keys or 'all' (default: all configured mods)")
    ap.add_argument("--mods-only", action="store_true",
                    help="only install mods into an existing install (default: all mods)")
    ap.add_argument("--mod-file", action="append", default=[], metavar="KEY=PATH",
                    help="use an already downloaded Drive zip (sha256-checked), e.g. fortress=C:\\Users\\you\\Downloads\\fortress.zip")
    ap.add_argument("--check-updates", action="store_true",
                    help="only check an existing install for client/mod updates")
    ap.add_argument("--update", action="store_true",
                    help="check, then install only out-of-date clients/mods")
    a = ap.parse_args(argv)
    if a.self_test:
        from quake_installer import selftest
        return selftest.run(gui=False)
    keys = [m["key"] for m in load_specs()]
    if a.mods.strip().lower() in ("", "all"):
        mods = keys
    else:
        mods = [k.strip() for k in a.mods.split(",") if k.strip()]
    for k in mods:
        if k not in keys:
            ap.error("unknown mod %r (choose from %s)" % (k, ", ".join(keys)))
    mod_files = dict(x.split("=", 1) for x in a.mod_file if "=" in x)

    if a.preset != "none":
        binds = dict(cfg.PRESET_VANILLA) if a.preset == "vanilla" else {}
        if a.preset == "vanilla":
            binds = dict(cfg.PRESET_VANILLA)
        elif a.preset == "wasd":
            binds = dict(cfg.PRESET_VANILLA)
            binds.update(cfg.PRESET_WASD)
        elif a.preset == "modern":
            binds = dict(cfg.PRESET_VANILLA)
            binds.update(cfg.PRESET_WASD)
            binds.update(cfg.PRESET_MODERN)
    elif a.movement is not None or a.weapons is not None:
        binds = cfg.binds_from_legacy(a.movement or "vanilla", a.weapons or "vanilla")
    else:
        binds = {}

    opts = Options(a.root, a.name, a.look, binds=binds,
                   write_bats=False, configs_only=a.configs_only,
                   mods=mods, mod_files=mod_files, mods_only=a.mods_only,
                   platform=host_platform())
    if a.check_updates or a.update:
        from quake_installer import updater
        from quake_installer.installer import Reporter
        note = updater.platform_mismatch_note(a.root, opts.platform)
        if note:
            print("NOTE: " + note)
        items = updater.check_updates(a.root, opts.platform)
        for it in items:
            print("  " + it.line())
        if a.update:
            up, failed = updater.apply_updates(opts, items, Reporter())
            print("updated: %d, failed: %d" % (len(up), len(failed)))
            return 1 if failed else 0
        return 0
    try:
        res = run_install(opts)
    except InstallError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print("INSTALL COMPLETE")
    print("  UnezQuake exe: %s" % res.unez_exe)
    print("  FTE exe      : %s" % res.fte_exe)
    if res.fte_fmf:
        print("  FTE fmf     : %s" % res.fte_fmf)
    for item in res.mods_installed:
        key, title, gd, src = item[0], item[1], item[2], item[3]
        clients = item[4] if len(item) > 4 else ["fte"]
        print("  mod OK       : %s -> %s/%s (%s)" % (title, "+".join(clients), gd, src))
    for key, title, msg in res.mods_failed:
        print("  mod FAILED   : %s\n    %s" % (title, msg))
    for w in res.warnings:
        print("  WARN: %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
