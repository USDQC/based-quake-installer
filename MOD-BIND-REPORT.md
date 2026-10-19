# Mod binds

Extra bind boxes per mod, taken from each mod's own docs or configs. Saved to `<gamedir>/binds.cfg`, run last in that mod.

- **Team Fortress** (README.TXT command + impulse summary): `+gren1`, `+gren2`, `special`, `reload`, `detpipe`, `impulse 22`, `impulse 39`, `impulse 40`, `impulse 69`, `inv`, `flaginfo`, `discard`, `saveme`, `dropammo`, `changeclass`
- **Thunderwalker CTF** (twdocs/impulses.htm): `impulse 22`, `impulse 20`, `impulse 21`, `impulse 23`, `impulse 47`, `impulse 69`, `impulse 160`, `impulse 180`, `impulse 181`, `impulse 200`, `impulse 141`
- **Rocket Arena** (readme.txt impulse reference): `impulse 68`, `impulse 69`, `impulse 70`, `impulse 71`, `impulse 72`
- **PainKeep** (IMPULSES.TXT): `impulse 21`, `impulse 30`, `impulse 32`, `impulse 33`, `impulse 34`, `impulse 35`, `impulse 36`, `impulse 38`, `impulse 50`, `impulse 69`
- **AirQuake (FTE)** (AUTOEXEC.CFG, AQALIAS.CFG): `+freelook`, `+extraleft`, `+extraright`, `+cczoomin`, `+cczoomout`, `liftcam`, `lockturret`, `impulse 9`
- **Quake Rally (FTE)** (RALLY.CFG, QRDOCS.TXT): `+accelerate`, `+reverse`, `+horn`, `+zoomin`, `+zoomout`, `impulse 40`, `impulse 43`, `impulse 50`, `impulse 150`, `impulse 151`, `impulse 201`, `impulse 120`, `impulse 130`
- **Get Rich Quake** (Readme.txt, gr_utils.qc): `impulse 120`, `impulse 22`, `impulse 121`
- **Rune Quake** (player commands docs, bindings.qc): `impulse 100`, `impulse 98`, `impulse 99`, `impulse 96`, `impulse 95`, `impulse 92`, `impulse 86`, `+hook`, `impulse 97`, `impulse 201`
- **Headhunters**, **Future vs Fantasy**: none (no documented binds).

Quick-use aliases (switch, fire while held, `impulse 69` back), checked in the QuakeC:

- **PainKeep** 1.11 (`pk111src.zip`, qwsrc): `pk_ChangeWeapon` impulses 30/33/34/35/36 (weapons.qc:1851-1905); 69 restores `lastweapon`/`pklastweapon` (weapons.qc:2450-2459), set in `W_SetCurrentAmmo` (weapons.qc:1285-1291); `W_WeaponFrame` runs impulses before `W_Attack` (weapons.qc:2581-2602). Grapple not offered: its harpoon stays out (fire again to reel in, impulse 50 to release).
- **Thunderwalker** 3.01 (`tw301qsv.zip`, twqwsrc): AirFist 47 (defs.qc:810, weapons.qc:1527), grapple 22 (weapons.qc:1479), 69 = `PreviousWeaponCommand` (weapons.qc:1849, 1942). Hook drops on release (grapple.qc:375-379) in PlayerPreThink (client.qc:1156), before `W_WeaponFrame` (client.qc:1358).

Tab conflicts (checked v1.6.5): no mod binds Tab to anything but `+showscores`. FTE's own `fte/default.cfg` has `+showteamscores`; the installer's `unbindall` + `bind TAB +showscores` replaces it.
