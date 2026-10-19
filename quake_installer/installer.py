"""Install orchestration (no GUI code here, so it can be tested headless).

This is an installer only: it downloads/extracts clients, writes autoexec.cfg,
always installs the configured mods, and writes FTE default.fmf with
DISABLEHOMEDIR so the engine skips the user home dir without helper .bat files.
It does not launch games, write .bat helpers, or create desktop shortcuts.
"""

import os
import shutil
import tempfile

from . import cfg, clients, download, extract, launchers, manifest, mods as modlib, sb_sources
from .constants import (
    FTE_DIRNAME, FTE_EXE_BY_PLATFORM, PAK0_MD5, PAK0_SIZE, PROTECTED_FILES, SHAREWARE_URLS,
    UNEZ_DIRNAME, UNEZ_EXE_BY_PLATFORM, host_platform,
)
from .download import Cancelled, DownloadError
from .extract import ExtractError


class InstallError(Exception):
    pass


class Options(object):
    def __init__(self, root, player_name, look, binds=None,
                 movement=None, weapons=None,
                 write_bats=False, configs_only=False, mods=None, mod_files=None,
                 mods_only=False, mod_binds=None, platform=None):
        self.root = root
        self.player_name = player_name
        self.look = look
        # binds: dict action_id -> key. Blank/missing skipped. Legacy CLI can pass
        # movement/weapons instead and we expand them via presets.
        if binds is not None:
            self.binds = dict(binds)
        else:
            self.binds = cfg.binds_from_legacy(movement or "vanilla", weapons or "vanilla")
        # write_bats kept for API compat but ignored — installer never writes .bat files.
        self.write_bats = False
        self.configs_only = configs_only
        # None / empty on a full install means "all configured mods".
        self.mods = list(mods) if mods is not None else None
        self.mod_files = dict(mod_files or {})
        self.mods_only = mods_only
        # mod_binds: {mod_key: {action_id: key}} optional per-gamedir binds
        self.mod_binds = dict(mod_binds or {})
        # Client platform whose engine builds get installed (always the running OS: windows/linux).
        self.platform = platform or host_platform()

    @property
    def unez_dir(self):
        return os.path.join(self.root, UNEZ_DIRNAME)

    @property
    def fte_dir(self):
        return os.path.join(self.root, FTE_DIRNAME)


class Result(object):
    def __init__(self):
        self.unez_exe = None
        self.fte_exe = None
        self.fte_source = None
        self.cfg_files = []
        self.launchers = []
        self.fte_fmf = None
        self.shareware_url = None
        self.pak0_md5 = None
        self.warnings = []
        self.mods_installed = []   # (key, title, gamedir, source, clients)
        self.mods_failed = []      # (key, title, message)
        self.manifest_path = None
        self.skipped_clients = []  # (client, reason)


class Reporter(object):
    """Callbacks used by the installer. The GUI supplies thread-safe versions."""

    def log(self, msg):
        print(msg)

    def step(self, index, total, title):
        print("[%d/%d] %s" % (index, total, title))

    def progress(self, done, total):
        pass


def _mkdirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        raise InstallError(
            "No permission to create %s.\nPick a folder you own (e.g. D:\\Games or "
            "%%USERPROFILE%%\\Games) or run the installer as administrator." % path)
    except OSError as exc:
        raise InstallError("Cannot create %s: %s" % (path, exc))


def _check_writable(path):
    probe = os.path.join(path, ".write-test.tmp")
    try:
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError as exc:
        raise InstallError("Folder is not writable: %s (%s)" % (path, exc))


def write_cfg(path, text, rep):
    """Write autoexec.cfg; back up a different pre-existing file once as .bak."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            old = fh.read()
        if old != text.encode("utf-8"):
            bak = path + ".bak"
            shutil.copy2(path, bak)
            rep.log("  backed up existing %s -> %s" % (os.path.basename(path), bak))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def cfg_targets(opts):
    """Where each client's autoexec.cfg goes.

    FTE reads autoexec.cfg through its game search path (id1/, plus qw/ and fte/ in
    AfterQuake); UnezQuake (ezQuake) does the same (id1/, qw/, ezquake/).
    The copy in id1/ is the one the engines actually exec; the copy next to the
    exe is for visibility/safety. The two client trees never share a file.
    """
    fte = [os.path.join(opts.fte_dir, "autoexec.cfg"),
           os.path.join(opts.fte_dir, "id1", "autoexec.cfg")]
    unez = [os.path.join(opts.unez_dir, "autoexec.cfg"),
            os.path.join(opts.unez_dir, "id1", "autoexec.cfg")]
    if os.path.isdir(os.path.join(opts.unez_dir, "ezquake")):
        unez.append(os.path.join(opts.unez_dir, "ezquake", "autoexec.cfg"))
    return fte, unez



AUTOEXEC_STUB = (
    "// autoexec.cfg -- generated by Based Quake Installer\n"
    "// Your name / binds / look live in id1/based.cfg (shared by every mod gamedir,\n"
    "// which finds it through the id1 fallback). Edit based.cfg or re-run the installer.\n"
    "exec based.cfg\n")


def installed_mod_dirs(opts):
    """[(spec, label, target)] for every configured mod whose gamedir exists."""
    out = []
    for spec in modlib.load_specs():
        for label, target in modlib.client_dirs(spec, opts.fte_dir, opts.unez_dir):
            if os.path.isdir(target):
                out.append((spec, label, target))
    return out


def write_mod_configs(opts, rep, result):
    """Every installed mod gamedir: merged autoexec.cfg (exec based.cfg ... exec binds.cfg)
    plus binds.cfg from the Mod binds tab (blank when none chosen)."""
    from . import binds_mods
    for key, binds in sorted((opts.mod_binds or {}).items()):
        bad = binds_mods.unknown_mod_bind_actions(key, binds)
        if bad:
            rep.log("  WARN: mod binds for %s: unknown action(s) %s dropped (known: %s)"
                    % (key, ", ".join(bad),
                       ", ".join(a[0] for a in binds_mods.actions_for(key)) or "none"))
        for k, mod_label, gen_label in binds_mods.key_conflicts(key, binds, opts.binds):
            rep.log("  NOTE: %s: %s is bound to both '%s' (mod) and '%s'; the mod bind "
                    "wins in that mod only (binds.cfg)" % (key, k, mod_label, gen_label))
    for spec, label, target in installed_mod_dirs(opts):
        key = spec["key"]
        if binds_mods.actions_for(key):
            cleaned = binds_mods.clean_mod_binds(key, (opts.mod_binds or {}).get(key) or {})
            text = binds_mods.render_mod_binds_cfg(key, cleaned, title=spec.get("title"))
            binds_path = os.path.join(target, "binds.cfg")
            write_cfg(binds_path, text, rep)
            if cleaned:
                rep.log("  wrote %s (%s, %d mod binds)" % (binds_path, label, len(cleaned)))
            result.cfg_files.append(binds_path)
        auto = binds_mods.merge_mod_autoexec(target)
        if auto not in result.cfg_files:
            result.cfg_files.append(auto)
    rep.log("  mod gamedirs: autoexec.cfg runs exec based.cfg (+ mod's own) + exec binds.cfg")


def write_configs(opts, rep, result):
    # First: it creates ezquake/, which cfg_targets() then includes.
    write_unez_sources(opts, rep, result)
    fte_targets, unez_targets = cfg_targets(opts)
    for client, targets in ((cfg.CLIENT_FTE, fte_targets), (cfg.CLIENT_UNEZ, unez_targets)):
        text = cfg.render_autoexec(client, opts.player_name, opts.binds, opts.look)
        text = text.replace("// autoexec.cfg for", "// based.cfg (exec'd by autoexec.cfg) for", 1)
        for p in targets:
            d = os.path.dirname(p)
            if os.path.basename(d).lower() == "id1":
                based = os.path.join(d, "based.cfg")
                write_cfg(based, text, rep)
                rep.log("  wrote %s" % based)
                result.cfg_files.append(based)
            write_cfg(p, AUTOEXEC_STUB.replace("\n", "\r\n"), rep)
            rep.log("  wrote %s" % p)
            result.cfg_files.append(p)
    write_mod_configs(opts, rep, result)


def write_unez_sources(opts, rep, result=None):
    """Merge-safe {unez}/ezquake/sb/sources.txt (server browser). Never fatal."""
    if not os.path.isdir(opts.unez_dir):
        return None
    try:
        path = sb_sources.write_sources(opts.unez_dir, log=rep.log)
    except OSError as exc:
        rep.log("  WARN: could not write server browser sources: %s" % exc)
        return None
    if result is not None and path not in result.cfg_files:
        result.cfg_files.append(path)
    return path


def all_mod_keys():
    return [m["key"] for m in modlib.load_specs()]


def resolve_mod_keys(opts):
    """Always install every configured mod unless CLI passed an explicit non-empty subset."""
    if not opts.mods:
        return all_mod_keys()
    return list(opts.mods)


def run_install(opts, rep=None, cancel_event=None):
    rep = rep or Reporter()
    result = Result()
    root = os.path.normpath(opts.root.strip().strip('"'))
    if not root or root in (".",):
        raise InstallError("Please choose an install folder.")
    opts.root = root

    for d in (root, opts.unez_dir, opts.fte_dir,
              os.path.join(opts.unez_dir, "id1"), os.path.join(opts.fte_dir, "id1")):
        _mkdirs(d)
    _check_writable(root)
    rep.log("Install root : %s" % root)
    rep.log("UnezQuake    : %s" % opts.unez_dir)
    rep.log("FTE          : %s" % opts.fte_dir)

    if opts.configs_only or opts.mods_only:
        steps = 3
        rep.step(1, steps, "Checking existing installs")
        result.unez_exe = find_unez(opts)
        result.fte_exe = find_fte(opts)
        if not result.unez_exe and not result.fte_exe:
            raise InstallError("UnezQuake/FTE not found under %s. Run a full Install first." % root)
        if opts.mods_only:
            work = tempfile.mkdtemp(prefix="quake-gui-mods-")
            try:
                rep.step(2, steps, "Installing all configured mods")
                man = manifest.load(root)
                install_mods(opts, rep, result, work, cancel_event, man=man)
                result.manifest_path = manifest.save(root, man)
                write_mod_configs(opts, rep, result)
            finally:
                shutil.rmtree(work, ignore_errors=True)
        else:
            rep.step(2, steps, "Writing autoexec.cfg files")
            write_configs(opts, rep, result)
        rep.step(3, steps, "Configuring FTE (default.fmf)")
        _configure_fte(opts, rep, result)
        return result

    work = tempfile.mkdtemp(prefix="quake-gui-install-")
    steps = 7
    try:
        man = manifest.load(root)
        man["platform"] = opts.platform
        install_clients(opts, rep, result, work, man, cancel_event, step_base=1, steps=steps)

        rep.step(3, steps, "Getting Quake shareware pak0.pak")
        unez_pak = os.path.join(opts.unez_dir, "id1", "pak0.pak")
        fte_pak = os.path.join(opts.fte_dir, "id1", "pak0.pak")
        existing = None
        for p in (unez_pak, fte_pak):
            if extract.pak0_is_valid(p):
                existing = p
                break
        if existing:
            rep.log("  valid pak0.pak already present (%s); skipping download" % existing)
            rep.progress(1, 1)
            pak_src = existing
            result.pak0_md5 = PAK0_MD5
        else:
            quake_zip = os.path.join(work, "quake106.zip")
            result.shareware_url = download.download_first(
                SHAREWARE_URLS, quake_zip, progress=rep.progress,
                cancel_event=cancel_event, log=rep.log)
            rep.log("  extracting resource.1")
            res1 = extract.extract_resource1(quake_zip, os.path.join(work, "resource.1"))
            rep.log("  extracting ID1/PAK0.PAK from resource.1 (LH5)")
            pak_src = extract.extract_pak0(res1, work, log=rep.log)
            size = os.path.getsize(pak_src)
            md5 = extract.file_md5(pak_src)
            result.pak0_md5 = md5
            rep.log("  pak0 size %d (expected %d), MD5 %s" % (size, PAK0_SIZE, md5))
            if md5 != PAK0_MD5 or size != PAK0_SIZE:
                raise InstallError(
                    "pak0.pak checksum mismatch (got %s, expected %s). The mirror may be "
                    "corrupt; try again later." % (md5, PAK0_MD5))
            rep.log("  OK: MD5 verified")

        rep.step(4, steps, "Installing pak0.pak into both id1 folders")
        for dst in (unez_pak, fte_pak):
            if os.path.abspath(dst) == os.path.abspath(pak_src):
                rep.log("  OK: %s (already valid)" % dst)
                continue
            try:
                shutil.copyfile(pak_src, dst)
            except PermissionError:
                raise InstallError("Cannot write %s (is the game running?)" % dst)
            rep.log("  OK: %s" % dst)

        rep.step(5, steps, "Installing all configured mods")
        install_mods(opts, rep, result, work, cancel_event, man=man)

        rep.step(6, steps, "Writing configs (id1/based.cfg + autoexec.cfg, mod gamedirs)")
        write_configs(opts, rep, result)

        rep.step(7, steps, "Configuring FTE (default.fmf / DISABLEHOMEDIR)")
        _configure_fte(opts, rep, result)
        result.manifest_path = manifest.save(root, man)
        rep.log("  wrote %s" % result.manifest_path)
        return result
    except (DownloadError, ExtractError) as exc:
        raise InstallError(str(exc))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def find_unez(opts):
    return extract.find_entry_ci(opts.unez_dir, UNEZ_EXE_BY_PLATFORM[opts.platform]) or \
        extract.find_entry_ci(opts.unez_dir, [n for v in UNEZ_EXE_BY_PLATFORM.values() for n in v])


def find_fte(opts):
    return extract.find_fte_exe(opts.fte_dir, FTE_EXE_BY_PLATFORM[opts.platform])


def install_unez_build(opts, rep, result, work, man, meta, cancel_event=None):
    name = meta.get("asset") or os.path.basename(meta["url"])
    zpath = os.path.join(work, name)
    download.download(meta["url"], zpath, progress=rep.progress, cancel_event=cancel_event)
    rep.log("  extracting %s" % name)
    stage = os.path.join(work, "unez-stage")
    shutil.rmtree(stage, ignore_errors=True)
    exe, files = clients.install_unez(opts.platform, zpath, opts.unez_dir, stage,
                                      protect=PROTECTED_FILES, log=rep.log)
    result.unez_exe = exe
    manifest.record(man, "client:unez", meta, files=files, platform=opts.platform)
    write_unez_sources(opts, rep, result)  # also covers Update of client:unez
    rep.log("  OK: %s (%s)" % (os.path.join(opts.unez_dir, exe), meta.get("version") or "?"))


def install_fte_build(opts, rep, result, work, man, meta, cancel_event=None):
    zpath = os.path.join(work, "fte.zip")
    download.download(meta["url"], zpath, progress=rep.progress, cancel_event=cancel_event)
    result.fte_source = meta.get("package")
    rep.log("  extracting FTE (%s)" % result.fte_source)
    stage = os.path.join(work, "fte-stage")
    shutil.rmtree(stage, ignore_errors=True)
    exe, files = clients.install_fte(opts.platform, zpath, opts.fte_dir, stage,
                                     protect=PROTECTED_FILES, log=rep.log)
    result.fte_exe = exe
    manifest.record(man, "client:fte", meta, files=files, platform=opts.platform)
    rep.log("  OK: detected FTE exe %s" % os.path.join(opts.fte_dir, exe))


def install_clients(opts, rep, result, work, man, cancel_event=None, step_base=1, steps=7):
    """Install unezQuake + FTE for opts.platform; skip (clearly) when no build exists."""
    label = clients.platform_label(opts.platform)
    rep.step(step_base, steps, "Downloading unezQuake (%s)" % label)
    try:
        meta = clients.resolve_unez(opts.platform)
    except DownloadError as exc:
        raise InstallError("Cannot reach unezQuake releases: %s" % exc)
    if meta is None:
        msg = "no unezQuake build published for %s; skipped" % label
        rep.log("  WARN: " + msg)
        result.skipped_clients.append(("unezQuake", msg))
        result.warnings.append(msg)
    else:
        try:
            install_unez_build(opts, rep, result, work, man, meta, cancel_event)
        except clients.ClientError as exc:
            raise InstallError(str(exc))

    rep.step(step_base + 1, steps, "Downloading FTE (%s)" % label)
    try:
        meta = clients.resolve_fte(opts.platform)
    except DownloadError as exc:
        raise InstallError("Cannot reach FTE builds: %s" % exc)
    if meta is None:
        msg = "no FTE build published for %s; skipped (FTE mods need another platform)" % label
        rep.log("  WARN: " + msg)
        result.skipped_clients.append(("FTE", msg))
        result.warnings.append(msg)
    else:
        try:
            install_fte_build(opts, rep, result, work, man, meta, cancel_event)
        except clients.ClientError as exc:
            raise InstallError(str(exc))


def install_mods(opts, rep, result, work, cancel_event=None, man=None):
    """Install all configured mods (or a CLI subset) into each mod's client tree(s)."""
    keys = resolve_mod_keys(opts)
    if not keys:
        rep.log("  no mods configured")
        return
    online, _err = modlib.load_specs_online(log=rep.log)
    specs = {m["key"]: m for m in online}
    for key in keys:
        spec = specs.get(key)
        if not spec:
            rep.log("  WARN: unknown mod %r skipped" % key)
            continue
        clients = ", ".join(spec.get("clients") or ["fte"])
        rep.log("  --- %s -> %s %s" % (spec["title"], clients, spec["gamedir"] + os.sep))
        if spec.get("needs_registered"):
            rep.log("  NOTE: %s" % spec.get("note", "needs registered Quake (pak1.pak)"))
        try:
            meta = {}
            src = modlib.install_mod(
                spec, opts.fte_dir, work, progress=rep.progress,
                cancel_event=cancel_event, log=rep.log,
                local_file=opts.mod_files.get(key), unez_dir=opts.unez_dir,
                meta_out=meta, protect=PROTECTED_FILES)
            if man is not None:
                manifest.record(man, "mod:" + key, meta,
                                extra={"source": src, "gamedir": spec["gamedir"]})
            result.mods_installed.append(
                (key, spec["title"], spec["gamedir"], src, list(spec.get("clients") or ["fte"])))
        except Cancelled:
            raise
        except (modlib.ModError, DownloadError, ExtractError, OSError) as exc:
            msg = str(exc)
            rep.log("  WARN: %s not installed: %s" % (spec["title"], msg))
            result.mods_failed.append((key, spec["title"], msg))
            result.warnings.append("%s not installed (see log)" % spec["title"])


def installed_mod_specs(opts):
    """Specs whose gamedir already has game data in at least one declared client tree."""
    out = []
    for spec in modlib.load_specs():
        for _label, target in modlib.client_dirs(spec, opts.fte_dir, opts.unez_dir):
            if modlib._has_game_files(target):
                out.append(spec)
                break
    return out


def _configure_fte(opts, rep, result):
    """Engine-side -nohome via default.fmf; no .bat helpers."""
    if not result.fte_exe:
        result.fte_exe = find_fte(opts)
    if not result.unez_exe:
        result.unez_exe = find_unez(opts)
    path = launchers.ensure_fte_default_fmf(opts.fte_dir, log=rep.log)
    result.fte_fmf = path
    rep.log("  FTE: run %s from the FTE folder (default.fmf disables home dir)."
            % (result.fte_exe or "fteqw*"))
    rep.log("  Mods: use the client's -game <gamedir> (or in-game gamedir) to load a mod.")


__all__ = ["Options", "Result", "Reporter", "run_install", "InstallError", "Cancelled"]
