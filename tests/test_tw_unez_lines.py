import os
from quake_installer import binds_mods as b

def test_tw_unez_lines(tmp_path):
    d = tmp_path / "ctf"; d.mkdir()
    (d / "autoexec.cfg").write_text("bind x y\nmtu 1450\n")
    p = b.merge_mod_autoexec(str(d))
    for _ in range(2):
        b.add_mod_client_lines(p, "thunderwalker", "unezQuake")
        b.merge_mod_autoexec(str(d))
    t = open(p).read()
    assert t.count("mtu 1300") == 1 and "mtu 1450" not in t
    assert t.count("cl_remote_capabilities") == 1 and ",setinfo,topcolor,bottomcolor\"" in t
    assert "bind x y" in t and t.index("mtu 1300") < t.index("exec binds.cfg")

def test_fte_untouched(tmp_path):
    d = tmp_path / "ctf"; d.mkdir()
    p = b.merge_mod_autoexec(str(d))
    assert not b.add_mod_client_lines(p, "thunderwalker", "FTE")
    assert "mtu" not in open(p).read()
