"""Check for updates / apply updates to an existing install (background-thread safe).

check_updates() only does HEAD / GitHub API calls and compares against the manifest.
apply_updates() re-downloads only the out-of-date components, overwriting engine
binaries and mod paks but never user cfgs (autoexec.cfg, binds.cfg, config.cfg,
default.fmf) and never wiping a gamedir.
"""

import os
import shutil
import tempfile

from . import clients, download, manifest, mods as modlib
from .download import DownloadError


class UpdateItem(object):
    def __init__(self, component, title, status, installed=None, remote=None, detail=""):
        self.component = component      # "client:unez" | "client:fte" | "mod:<key>"
        self.title = title
        self.status = status
        self.installed = installed
        self.remote = remote
        self.detail = detail

    @property
    def needs_update(self):
        return self.status in (manifest.STATUS_OUTDATED, manifest.STATUS_MISSING)

    def line(self):
        d = (" — " + self.detail) if self.detail else ""
        return "%-28s %s%s" % (self.title, self.status, d)


# CH - Selection model for the update dialog: only rows apply_updates() can install
# are checkable, and "not installed" stays out of the default so Update never
# installs a mod the user did not ask for.
SELECT_MODE_DEFAULT = "default"
SELECT_MODE_ALL = "all"
SELECT_MODE_NONE = "none"
SELECT_MODE_ENGINES = "engines"
SELECT_MODE_MODS = "mods"

SELECT_MODES = (SELECT_MODE_DEFAULT, SELECT_MODE_ALL, SELECT_MODE_NONE,
                SELECT_MODE_ENGINES, SELECT_MODE_MODS)


def is_selectable(item):
    """True when apply_updates() can install this item (outdated or missing)."""
    return item.status in (manifest.STATUS_OUTDATED, manifest.STATUS_MISSING)


def select_components(items, mode=SELECT_MODE_DEFAULT):
    """Component ids to check for one dialog preset.

    default: out-of-date rows only ("update available").
    all: every selectable row, including "not installed".
    engines: selectable client:* rows (unezQuake and FTE).
    mods: selectable mod:* rows (mods and packs).
    none: nothing.
    """
    if mode not in SELECT_MODES:
        raise ValueError("unknown selection mode %r" % (mode,))
    chosen = set()
    if mode == SELECT_MODE_NONE:
        return chosen
    for item in items:
        if not is_selectable(item):
            continue
        if mode == SELECT_MODE_DEFAULT and item.status == manifest.STATUS_MISSING:
            continue
        if mode == SELECT_MODE_ENGINES and not item.component.startswith("client:"):
            continue
        if mode == SELECT_MODE_MODS and not item.component.startswith("mod:"):
            continue
        chosen.add(item.component)
    return chosen


# CH - Human summary for Check for updates: engines and mods are reported
# separately, and "up to date" is never claimed when a check failed.
_ENGINE_NAMES = {"client:unez": "unezQuake", "client:fte": "FTE"}
_ENGINE_PHRASES = {
    manifest.STATUS_OK: "up to date",
    manifest.STATUS_OUTDATED: "update available",
    manifest.STATUS_MISSING: "not installed",
    manifest.STATUS_ERROR: "check failed",
    manifest.STATUS_UNAVAILABLE: "no build for this platform",
    manifest.STATUS_PLATFORM: "installed for another platform",
}


def _join_names(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    if len(names) == 2:
        return "%s and %s" % (names[0], names[1])
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def check_summary(items):
    """Return (headline, lines) describing an update check at a glance.

    "not installed" counts as an available install/update; a failed check or an
    unavailable build only asks for attention, so it never says "up to date".
    """
    items = list(items)
    if not items:
        return "Nothing to check.", []
    engines = [i for i in items if i.component.startswith("client:")]
    mods = [i for i in items if i.component.startswith("mod:")]
    lines = []
    if engines:
        names = [_ENGINE_NAMES.get(i.component, i.title) for i in engines]
        if all(i.status == manifest.STATUS_OK for i in engines):
            verb = "is" if len(names) == 1 else "are"
            lines.append("Engines: %s %s up to date." % (_join_names(names), verb))
        else:
            phrases = ["%s %s" % (_ENGINE_NAMES.get(i.component, i.title),
                                  _ENGINE_PHRASES.get(i.status, i.status))
                       for i in engines]
            lines.append("Engines: %s." % "; ".join(phrases))
    if mods:
        if all(i.status == manifest.STATUS_OK for i in mods):
            lines.append("Mods: all up to date (%d)." % len(mods))
        else:
            parts = []

            def add(n, one, many):
                if n:
                    parts.append(one if n == 1 else many % n)

            add(sum(1 for i in mods if i.status == manifest.STATUS_OUTDATED),
                "1 update available", "%d updates available")
            add(sum(1 for i in mods if i.status == manifest.STATUS_MISSING),
                "1 not installed", "%d not installed")
            add(sum(1 for i in mods if i.status == manifest.STATUS_ERROR),
                "1 check failed", "%d checks failed")
            add(sum(1 for i in mods if i.status == manifest.STATUS_UNAVAILABLE),
                "1 without a build for this platform",
                "%d without a build for this platform")
            add(sum(1 for i in mods if i.status == manifest.STATUS_PLATFORM),
                "1 for another platform", "%d for another platform")
            lines.append("Mods: %s." % ", ".join(parts))
    has_updates = any(i.status in (manifest.STATUS_OUTDATED, manifest.STATUS_MISSING)
                      for i in items)
    has_issues = any(i.status in (manifest.STATUS_ERROR, manifest.STATUS_UNAVAILABLE,
                                  manifest.STATUS_PLATFORM) for i in items)
    if has_updates:
        headline = "Updates available."
    elif has_issues:
        headline = "No updates available, but some checks need attention."
    else:
        headline = "Everything is up to date."
    return headline, lines


def _describe(meta):
    if not meta:
        return ""
    if meta.get("version"):
        return str(meta["version"])
    bits = []
    if meta.get("last_modified"):
        bits.append(meta["last_modified"])
    if meta.get("size"):
        bits.append("%d bytes" % meta["size"])
    return ", ".join(bits)


def _remote_mod(spec):
    """What Drive currently offers for one mod (from mods.json / the built-in table)."""
    url = (spec.get("url") or "").strip()
    if not url or url == modlib.PLACEHOLDER:
        return {"error": "no Google Drive link configured for this mod yet"}
    if not spec.get("sha256"):
        return {"error": "mods.json has no sha256 for this mod"}
    return {"file": spec.get("file"), "url": url, "version": spec.get("version"),
            "sha256": spec["sha256"].lower(), "size": spec.get("size")}


def installed_platform(root):
    """Platform recorded in the manifest, or None (no / pre-1.6 manifest)."""
    return manifest.load(root).get("platform")


def platform_mismatch_note(root, running):
    """Message when the install was made on another OS (else '')."""
    inst = installed_platform(root)
    if inst and inst != running:
        return ("This install was made for %s, but this installer runs on %s. Client "
                "updates are skipped (no cross-platform install); run Install here to "
                "install %s clients." % (clients.platform_label(inst),
                                         clients.platform_label(running),
                                         clients.platform_label(running)))
    return ""


def _client_dirs(spec, root, opts=None):
    # CH - Mods follow the selected engines: an unselected client's dir is None, so
    # its gamedirs are never created or updated.
    from .constants import FTE_DIRNAME, UNEZ_DIRNAME
    if opts is not None:
        return modlib.client_dirs(spec, opts.fte_dir, opts.unez_dir)
    return modlib.client_dirs(spec, os.path.join(root, FTE_DIRNAME),
                              os.path.join(root, UNEZ_DIRNAME))


def check_updates(root, platform, specs=None, log=print, head=download.head,
                  resolve_unez=clients.resolve_unez, resolve_fte=clients.resolve_fte,
                  get_text=None, opts=None):
    """Return [UpdateItem]. Network errors become STATUS_ERROR items (never raise).

    Mods: mods.json is fetched from Drive (one stable link) and each mod's
    version/sha256 is compared with what the manifest recorded.
    opts with existing=True (mods-only): the clients are the user's own, so only
    mods/packs are checked, in opts.unez_dir / opts.fte_dir."""
    existing = bool(opts is not None and getattr(opts, "existing", False))
    man = manifest.load(root)
    mismatch = bool(man.get("platform")) and man["platform"] != platform
    comps = man.get("components", {})
    items = []
    label = clients.platform_label(platform)

    for comp, title, resolver in (("client:unez", "unezQuake (%s)" % label, resolve_unez),
                                  ("client:fte", "FTE (%s)" % label, resolve_fte)):
        if existing:
            continue  # user's own client: never updated by us
        if opts is not None and comp == "client:unez" and not getattr(opts, "uses_unez", True):
            continue  # not selected in Settings
        if opts is not None and comp == "client:fte" and not getattr(opts, "uses_fte", True):
            continue
        if mismatch:
            items.append(UpdateItem(comp, title, manifest.STATUS_PLATFORM, comps.get(comp), None,
                                    "installed for %s; skipped"
                                    % clients.platform_label(man["platform"])))
            continue
        log("  checking %s" % title)
        try:
            remote = resolver(platform)
        except DownloadError as exc:
            remote = {"error": str(exc)}
        inst = comps.get(comp)
        st = manifest.compare(inst, remote, platform)
        if st == manifest.STATUS_ERROR:
            detail = remote["error"][:200]
        elif st == manifest.STATUS_UNAVAILABLE:
            detail = "skipped"
        else:
            detail = "installed %s, latest %s" % (_describe(inst) or "unknown",
                                                  _describe(remote) or "?")
        items.append(UpdateItem(comp, title, st, inst, remote, detail))

    index_err = None
    if specs is None:
        log("  checking mods.json on Google Drive")
        specs, index_err = modlib.load_specs_online(log=log, get_text=get_text)
    for spec in specs:
        if not _client_dirs(spec, root, opts):
            continue  # needs an engine that is not selected
        if spec.get("binds_only"):
            continue  # server-side mod: nothing downloaded, nothing to update
        comp = "mod:" + spec["key"]
        log("  checking mod %s" % spec["title"])
        remote = {"error": "mods.json: " + index_err} if index_err else _remote_mod(spec)
        inst = comps.get(comp)
        if remote.get("error"):
            st = manifest.STATUS_ERROR
        elif inst is None and not _mod_present(root, spec, opts):
            st = manifest.STATUS_MISSING
        else:
            st = manifest.compare(inst or {}, remote)
        if remote.get("error"):
            detail = remote["error"][:200]
        elif st == manifest.STATUS_OUTDATED:
            detail = "installed %s, Drive %s" % (
                (inst or {}).get("version") or "old mirror build", remote.get("version") or "?")
        else:
            detail = ""
        item = UpdateItem(comp, spec["title"], st, inst, remote, detail)
        item.spec = spec
        items.append(item)
    return items


def _mod_present(root, spec, opts=None):
    for label, target in _client_dirs(spec, root, opts):
        if modlib.is_present(spec, target):
            return True
    return False


def apply_updates(opts, items, rep, cancel_event=None):
    """Download + install only items that need it. Returns (updated, failed)."""
    from . import installer
    existing = bool(getattr(opts, "existing", False))
    if existing:
        opts.root = installer.existing_manifest_root(opts)
        items = [i for i in items if not i.component.startswith("client:")]
    if not getattr(opts, "uses_unez", True):
        items = [i for i in items if i.component != "client:unez"]
    if not getattr(opts, "uses_fte", True):
        items = [i for i in items if i.component != "client:fte"]
    todo = [i for i in items if i.needs_update]
    updated, failed = [], []
    if not todo:
        return updated, failed
    man = manifest.load(opts.root)
    if man.get("platform") and man["platform"] != opts.platform:
        todo = [i for i in todo if not i.component.startswith("client:")]
        rep.log("  NOTE: " + platform_mismatch_note(opts.root, opts.platform))
    else:
        man["platform"] = opts.platform
    result = installer.Result()
    work = tempfile.mkdtemp(prefix="quake-gui-update-")
    try:
        specs = None
        for n, item in enumerate(todo, start=1):
            rep.step(n, len(todo), "Updating %s" % item.title)
            try:
                if item.component == "client:unez":
                    installer.install_unez_build(opts, rep, result, work, man, item.remote,
                                                 cancel_event)
                elif item.component == "client:fte":
                    installer.install_fte_build(opts, rep, result, work, man, item.remote,
                                                cancel_event)
                else:
                    key = item.component.split(":", 1)[1]
                    spec = getattr(item, "spec", None)
                    if spec is None:
                        if specs is None:
                            specs = {m["key"]: m for m in
                                     modlib.load_specs_online(log=rep.log)[0]}
                        spec = specs[key]
                    meta = {}
                    src = modlib.install_mod(
                        spec, opts.fte_dir, work, progress=rep.progress,
                        cancel_event=cancel_event, log=rep.log, unez_dir=opts.unez_dir,
                        meta_out=meta,
                        protect=(installer.EXISTING_PROTECTED if existing
                                 else installer.PROTECTED_FILES),
                        ci_protect=existing)
                    manifest.record(man, item.component, meta,
                                    extra={"source": src, "gamedir": spec["gamedir"]})
                    # Newly added gamedirs need the usual autoexec merge + binds.cfg
                    # (never overwrites an existing binds.cfg).
                    from . import binds_mods
                    for label, target in ([] if modlib.is_pack(spec) else
                                          modlib.client_dirs(spec, opts.fte_dir,
                                                             opts.unez_dir)):
                        cdir = opts.cfg_dir_for(label, target) if existing else target
                        extra = [target] if cdir != target else []
                        binds_mods.merge_mod_autoexec(cdir, extra_dirs=extra)
                        binds_mods.ensure_switch_hook(cdir, label, extra_dirs=extra)
                updated.append(item)
                manifest.save(opts.root, man)  # save as we go
            except download.Cancelled:
                raise
            except Exception as exc:
                rep.log("  WARN: %s update failed: %s" % (item.title, exc))
                failed.append((item, str(exc)))
        if result.fte_exe and not existing and opts.fte_dir:
            from . import launchers
            launchers.ensure_fte_default_fmf(opts.fte_dir, log=rep.log)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return updated, failed
