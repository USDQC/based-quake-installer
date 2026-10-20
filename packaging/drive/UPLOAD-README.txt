Based Quake Installer - Google Drive upload set

Contents: one <gamedir>.zip per mod (airquake, painkeep, hh, fortress, ctf, arena, fvf,
rally, grq), mods.json (gamedir, version, sha256, size, clients, url) and SHA256SUMS.txt.
Rune Quake has no zip (binds only).

Upload: put the 9 zips and mods.json in one Drive folder, unchanged.
Share: "Anyone with the link" (Viewer). Send back the 10 links for mods.json / MODS_INDEX_URL.
Update: Drive > Manage versions > Upload new version (keeps the link). A changed zip needs a
new mods.json too, or the installer refuses it (sha256 mismatch). Rebuild with:
  python3 packaging/drive/build_drive_zips.py <gamedirs folder> <out folder>

Packs (added later): skins.zip (qw/skins, both clients) and sprays.zip (qw/sprays,
unezQuake only), each with top folder qw/. Upload both as new files and send their
links; upload mods.json as a new version of the existing file (same link). Rebuild
just the packs with:
  python3 packaging/drive/build_drive_zips.py <staged> <out> --only skins --only sprays
