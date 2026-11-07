import os
from quake_installer import binds_mods as bm


def _build(tmp, key, client, runs=1, mod_text=None):
    d = os.path.join(tmp, key)
    os.makedirs(d, exist_ok=True)
    if mod_text:
        with open(os.path.join(d, "autoexec.cfg"), "w") as fh:
            fh.write(mod_text)
    for _ in range(runs):
        p = bm.merge_mod_autoexec(d)
        bm.add_mod_client_lines(p, key, client)
        bm.add_saved_cfg_and_last_lines(p, key, client)
    with open(p, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def test_fte_saved_cfg_after_binds(tmp_path):
    t = _build(str(tmp_path), "ctf", "FTE", runs=3, mod_text="bind x foo\n")
    lines = [l for l in t.split("\n") if l.strip()]
    assert lines[-1] == "exec fte.cfg"
    assert t.count("exec fte.cfg") == 1
    assert t.index("exec binds.cfg") < t.index("exec fte.cfg")
    assert "bind x foo" in t


def test_unez_saved_cfg_before_binds(tmp_path):
    t = _build(str(tmp_path), "ctf", "unezQuake", runs=3)
    assert t.count("exec configs/config.cfg") == 1
    assert t.index("exec based.cfg") < t.index("exec configs/config.cfg") < t.index("exec binds.cfg")


def test_hh_impulses_last_both_clients(tmp_path):
    want = ['bind %d "impulse %d"' % (n, n) for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)]
    for client in ("FTE", "unezQuake"):
        t = _build(str(tmp_path / client), "hh", client, runs=3, mod_text="exec hh.cfg\n")
        lines = [l for l in t.split("\n") if l.strip()]
        assert lines[-10:] == want
        for w in want:
            assert t.count(w) == 1
        assert "exec hh.cfg" in t


def test_other_mods_no_impulse_binds(tmp_path):
    t = _build(str(tmp_path), "ctf", "FTE")
    assert "impulse" not in t
