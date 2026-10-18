# Per-mod bind research (Quake GUI installer v1.6.0)

Research date: 2026-10-05, done on the original public mod archives (the same files the Drive zips
listed in `quake_installer/mods.py` are built from).

**Rules:** Only actions grounded in shipped `.cfg`, readmes/`IMPULSES.TXT`, or wiki/docs are listed.
No invented binds. Client archives contained **no QuakeC `*.qc` source** (compiled `progs.dat` / paks only).
Server-side QC (e.g. Thunderwalker `tw301qsv`) was not in the client packs we install.

**Write approach (implemented):** shared vanilla QW+weapons → each engine tree `id1/autoexec.cfg`.
Per-mod optional fields → `{client}/{gamedir}/binds.cfg` plus `exec binds.cfg` appended to that
gamedir’s `autoexec.cfg`. FTE-only mods write FTE tree only; dual mods write both.

**GUI wired:** Mod binds notebook tabs for every mod in `MOD_BIND_ACTIONS`
(`fortress`, `thunderwalker`, `arena`, `painkeep`, `airquake`, `rally`, `grq`, `runequake`).
Skipped UI: `hh`, `fvf` (see below).

---

## airquake (FTE-only)

**Files:** `airq102/AUTOEXEC.CFG`, `CONFIG.CFG`, `AQALIAS.CFG`, map `*.CFG`.
**QC:** none in archive.
**Custom (from AUTOEXEC + AQALIAS):**
| id | command | label | source |
|----|---------|-------|--------|
| freelook | +freelook | Free look | AUTOEXEC / AQALIAS (impulse 104/105) |
| extraleft / extraright | +extraleft / +extraright | Extra left/right | AUTOEXEC / AQALIAS |
| cczoomin / cczoomout | +cczoomin / +cczoomout | Cockpit zoom | AUTOEXEC / AQALIAS |
| liftcam | liftcam | Lift camera | AUTOEXEC (alias → impulse 20) |
| lockturret | lockturret | Lock turret | AUTOEXEC (alias → impulse 21) |
| impulse9 | impulse 9 | Slot 9 | AUTOEXEC |

**Wiki:** limited public bind tables; cfg is authoritative.
**UI:** wired (FTE gamedir only). AirQuake ships its own AUTOEXEC — installer `binds.cfg` is additive via exec.

---

## painkeep (FTE + unez)

**Files:** `IMPULSES.TXT`, `README.TXT`, `SERVER.CFG`.
**QC:** none.
**Custom (IMPULSES.TXT):** impulse 21/22/31 grapple; 30 AirFist; 32 chain LG; 33–36 inventory toys;
38 inv stats; 50 release harpoon; 69 previous weapon; plus hub/status impulses 200/201/225/253
(admin-ish — not all exposed in UI).
**Wiki / PlanetQuake mirrors:** [pk11read.txt](http://ftp.zx.net.nz/pub/archive/ftp.gamers.org/pub/games/idgames2/partial_conversions/painkeep/pk11read.txt),
[planetquake.fr Painkeep](https://planetquake.fr/quake-1-mods/painkeep.html) — confirm 1 cycles inventory, 9 harpoon, optional direct impulses.
**UI:** wired (direct-select subset). Keys 1–8 still covered by shared vanilla weapons.

---

## hh / Headhunters (FTE + unez)

**Files:** `Hh/Readme.txt` only (client pak).
**Custom binds:** readme mentions Grapple Gun but **no impulse table / cfg binds**.
**UI:** skipped (`MOD_BIND_SKIP`). Needs UI later if a documented impulse list is found.

---

## fortress / Team Fortress (FTE + unez)

**Files:** `tf28/FORTRESS/README.TXT`, `tf29qw/README.TXT` (Command + Impulse Summary).
**QC:** none in client zips.
**Custom (README Command Summary):** `+gren1`, `+gren2`, `special`, `reload`, `detpipe`,
`inv`, `flaginfo`, `discard`, `saveme`, `dropammo`, `changeclass`; impulses 22/39 hook, 40 axe, 69 last weapon.
**Wiki / archives:**
- [PlanetFortress TF configs](https://www.quaddicted.com/files/webarchive/www.planetfortress.com/tfguide/configs.html) (`+gren1`/`+gren2`/`special`)
- [QWTF TF-readme.TXT](https://github.com/QWTF/server/blob/master/TF-readme.TXT)
- [quake.fandom TeamFortress](https://quake.fandom.com/wiki/TeamFortress) (impulse lists; prefer README aliases for 2.8/2.9)
**UI:** wired.

---

## thunderwalker / ctf (FTE + unez)

**Files:** `tw301/twdocs/impulses.htm`, `overview.htm`, `readme.1st`, ThreeWave `3wctfc/readme.txt`.
**QC:** none in client pack (server source is a separate archive).
**Custom (impulses.htm):** 20 throw ammo, 21 throw weapon, 22 harpoon, 23 flag status, 47 airfist,
69 previous weapon, 160 flare, 180/181 rune, 200 teleporter, 141 ID.
**Wiki:** [Threewave Capture (Fandom)](https://quake.fandom.com/wiki/Threewave_Capture) — impulse 22 hook, 21/23, etc.
**UI:** wired.

---

## arena / Rocket Arena Final 1.2 (FTE + unez)

**Files:** `readme.txt` (Impulse Quick Reference). Maps/sounds pak only — no cfg binds.
**Custom:** impulse 68 stats, 69 position, 70 break, 71/72 status-bar layout.
**Wiki / mirrors:** [Frag-Net Rocket Arena](https://frag-net.com/mod_quake_arena.html) (same impulses).
**UI:** wired.

---

## fvf / Future vs Fantasy (FTE-only)

**Files:** `fvf4/readme.txt` (+ optional client pak).
**Explicit:** “No Impulses to Bind / No Aliases to Learn”.
**UI:** skipped.

---

## rally / Quake Rally (FTE-only)

**Files:** `RALLY/RALLY.CFG`, `CONFIG.CFG`, `QRDOCS.TXT`.
**Custom:** `+accelerate`, `+reverse`, `+horn`, `+zoomin`/`+zoomout`, impulses 40 camera,
43 in-car, 50 headlights, 120–130 sway, 150/151 observer, 201 change car (from QRDOCS + RALLY.CFG).
**UI:** wired (FTE only). Mod ships heavy CONFIG — our binds.cfg is additive.

---

## QuakeC source note

Searched all extracted client payloads for `*.qc` / `*.src`: **0 files**.
Impulse behavior inferred from readmes / cfg aliases only. Do not invent QC-only impulses
without a source or doc hit.

## Recommended next steps (research-only leftovers)

- Headhunters: find grapple impulse from server docs or QC mirror before UI.
- PainKeep: optional hub/SFX impulses (200/201/253) if users ask.
- AirQuake/Rally: consider not overwriting mod-shipped autoexec; current design appends `exec binds.cfg` only.

---

## grq — Get Rich Quake 1.1 (FTE + unez)

**Files:** `grqcl_11.zip` (pak0.pak, gfx/conback.lmp, Readme.txt), `grqsv11a.zip` (progs.dat, qwprogs.dat, NQ + QW QuakeC source).
**QW:** yes — server pack ships `qwprogs.dat` + `qwprogs/*.qc`; Readme documents `qwsv +gamedir grq`. So both clients.
**QC:** `qwprogs/gr_utils.qc` `GR_SetAliases` stuffs `alias cashbox impulse 120`, `alias grq_scores impulse 121`, `alias hook impulse 22`; `GR_ImpulseCommands` handles 120/121. Chasecam aliases (180–182) are NQ-only, not listed.
| id | command | label | source |
|----|---------|-------|--------|
| cashbox | impulse 120 | Cashbox (drop/fill/status) | Readme COMMAND SUMMARY + gr_utils.qc |
| hook | impulse 22 | Grappling hook | Readme + gr_utils.qc |
| grq_scores | impulse 121 | Team scores | Readme + gr_utils.qc |

## runequake — Rune Quake (FTE + unez), binds only since v1.5.2

Rune Quake is a **server-side** QuakeC mod (no client pak). The installer downloads/installs nothing for
it: it only creates `{client}/runequake/binds.cfg` + `autoexec.cfg` (`exec binds.cfg`) for both
clients. `needs_registered` is off. An experimental v1.5.1 FTEQCC server build was
kept outside the project and is not part of this repository.

**Binds (Playing "Player Commands", bindings.qc `player_init_impulse_alias`, defs.qc IMP_*):**
| id | command | label |
|----|---------|-------|
| rune_use | impulse 100 | rune-use |
| rune_delete | impulse 98 | rune-delete |
| rune_tell | impulse 99 | rune-tell |
| show_riders | impulse 96 | show-riders |
| fix_angles | impulse 95 | fix-angles |
| best_weapon | impulse 92 | best-weapon |
| weapon_mode | impulse 86 | weapon-mode |
| hook | +hook | +hook alias (IMP_HOOK_ON/OFF 88/87) |
| show_players | impulse 97 | show-players |
| observer | impulse 201 | observer menu |
