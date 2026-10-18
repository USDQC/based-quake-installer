Based Quake Installer - Google Drive upload set
================================================

What's here
-----------
  airquake.zip   4,559,986 bytes  1.03                   FTE only
  painkeep.zip  13,277,699 bytes  1.11                   FTE + unezQuake
  hh.zip         5,538,546 bytes  3.0                    FTE + unezQuake
  fortress.zip   4,169,491 bytes  2.8+2.9qw              FTE + unezQuake
  ctf.zip       17,419,183 bytes  3wctfc+tw3.01          FTE + unezQuake
  arena.zip      6,956,678 bytes  1.2                    FTE + unezQuake
  fvf.zip        7,467,292 bytes  4+clientpak2.09.21     FTE only
  rally.zip     13,626,962 bytes  1.2+lo1                FTE only
  grq.zip          632,122 bytes  1.1                    FTE + unezQuake
  mods.json      the index the installer reads (one entry per mod: gamedir, version,
                 sha256, size, clients, url)
  SHA256SUMS.txt  checksums of the zips (same values as in mods.json)

  Total: 73,647,959 bytes (about 74 MB) in 9 zips. Rune Quake has no zip (binds only).

Each zip has one top-level folder named after the gamedir (fortress/, ctf/, ...).
The installer downloads it, checks the sha256, and unzips it into each client's folder.

1. Upload
---------
Upload all 9 zips AND mods.json to one Google Drive folder.
Don't rename the files, and don't unzip or re-zip them.

2. Share
--------
For each of the 10 files: Share > General access > "Anyone with the link" (Viewer).
(If the folder itself is shared that way, the files inside inherit it.)

3. Send back the links
----------------------
Send all 10 share links (Share > Copy link), e.g.
  https://drive.google.com/file/d/1AbC.../view?usp=sharing
Then we:
  - put each zip link into mods.json ("url": PASTE_DRIVE_LINK -> your link),
  - put the mods.json link into the installer (MODS_INDEX_URL),
  - send you the filled-in mods.json.
Upload that filled-in mods.json as a new version of the mods.json already on Drive
(step 4), so its link never changes.

4. Updating a mod later (or mods.json)
--------------------------------------
Use Drive's Manage versions, not a fresh upload, so the share link stays the same:
  right-click the file > File information > Manage versions > Upload new version.
Whenever a zip changes, mods.json must change with it (new sha256, size and version),
and it must be replaced the same way. Otherwise the installer refuses that mod with
"sha256 mismatch" (on purpose: it never installs a file it can't verify).
Rebuild both with:
  python3 packaging/drive/build_drive_zips.py <folder of final gamedirs> <out folder>
That keeps the links already in out/mods.json; edit "version" by hand or pass --version key=VER.
Installed copies get "update available" when a mod's version or sha256 on Drive changes.

Notes
-----
- fortress.zip contains servcfg.zip. That's a 1997 server-admin vote kit shipped inside
  tf28.zip, and the old installer never unpacked it either.
- fvf.zip: fvf4 with the FvF client pak 2.09.21 (Pak0.pak) on top, as the pak's readme says.
  The pak's short ReadMe.txt replaces fvf4's readme.txt; the full fvf4.txt doc is kept.
- No zip is over 25 MB, so Drive normally serves them directly. Its "can't scan for viruses"
  confirm page is handled anyway.
