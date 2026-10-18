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


def check_updates(root, platform, specs=None, log=print, head=download.head,
                  resolve_unez=clients.resolve_unez, resolve_fte=clients.resolve_fte,
                  get_text=None):
    """Return [UpdateItem]. Network errors become STATUS_ERROR items (never raise).

    Mods: mods.json is fetched from Drive (one stable link) and each mod's
    version/sha256 is compared with what the manifest recorded."""
    man = manifest.load(root)
    mismatch = bool(man.get("platform")) and man["platform"] != platform
    comps = man.get("components", {})
    items = []
    label = clients.platform_label(platform)

    for comp, title, resolver in (("client:unez", "unezQuake (%s)" % label, resolve_unez),
                                  ("client:fte", "FTE (%s)" % label, resolve_fte)):
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
        if spec.get("binds_only"):
            continue  # server-side mod: nothing downloaded, nothing to update
        comp = "mod:" + spec["key"]
        log("  checking mod %s" % spec["title"])
        remote = {"error": "mods.json: " + index_err} if index_err else _remote_mod(spec)
        inst = comps.get(comp)
        if remote.get("error"):
            st = manifest.STATUS_ERROR
        elif inst is None and not _mod_present(root, spec):
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


def _mod_present(root, spec):
    from .constants import FTE_DIRNAME, UNEZ_DIRNAME
    for label, target in modlib.client_dirs(spec, os.path.join(root, FTE_DIRNAME),
                                           os.path.join(root, UNEZ_DIRNAME)):
        if modlib._has_game_files(target):
            return True
    return False


def apply_updates(opts, items, rep, cancel_event=None):
    """Download + install only items that need it. Returns (updated, failed)."""
    from . import installer
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
                        meta_out=meta, protect=installer.PROTECTED_FILES)
                    manifest.record(man, item.component, meta,
                                    extra={"source": src, "gamedir": spec["gamedir"]})
                    # Newly added gamedirs need the usual autoexec merge + binds.cfg
                    # (never overwrites an existing binds.cfg).
                    from . import binds_mods
                    for _label, target in modlib.client_dirs(spec, opts.fte_dir,
                                                             opts.unez_dir):
                        binds_mods.merge_mod_autoexec(target)
                updated.append(item)
                manifest.save(opts.root, man)  # save as we go
            except download.Cancelled:
                raise
            except Exception as exc:
                rep.log("  WARN: %s update failed: %s" % (item.title, exc))
                failed.append((item, str(exc)))
        if result.fte_exe:
            from . import launchers
            launchers.ensure_fte_default_fmf(opts.fte_dir, log=rep.log)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return updated, failed
