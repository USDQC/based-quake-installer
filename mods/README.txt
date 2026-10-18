Mods download only from the USDQC Google Drive: one <gamedir>.zip per mod, checked against the
sha256 in mods.json, then unzipped into each client's gamedir. This folder is no longer
searched for ModDB / idgames archives.

To install a Drive zip you already downloaded (it is still sha256-checked):
  installer_cli.py --mods-only --mods fortress --mod-file fortress=path\to\fortress.zip

  Mod                         Drive zip       clients
  --------------------------  --------------  ---------------
  AirQuake 1.03               airquake.zip    FTE only
  PainKeep 1.11               painkeep.zip    FTE + unezQuake
  Headhunters 3.0             hh.zip          FTE + unezQuake
  Team Fortress 2.8+2.9 QW    fortress.zip    FTE + unezQuake
  Thunderwalker (3wave+TW)    ctf.zip         FTE + unezQuake
  Rocket Arena (Final 1.2)    arena.zip       FTE + unezQuake
  Future vs Fantasy 4 + pak   fvf.zip         FTE only
  Quake Rally 1.2 + lo1       rally.zip       FTE only
  Get Rich Quake 1.1          grq.zip         FTE + unezQuake
  Rune Quake                  (none: server-side, binds only)

No Slipgate. Registered Quake: copy your own pak1.pak into each tree's id1 folder where a mod needs it.
