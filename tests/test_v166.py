"""v1.6.6: unezQuake square pixels (Software look) and crosshair 1."""

import unittest

from quake_installer import cfg

# Cvars registered by unezQuake 2.1.1 (src/r_texture_cvars.c, r_draw.c, vid_sdl2.c, cl_view.c).
UNEZ_CVARS = {"gl_texturemode", "gl_texturemode_viewmodels", "gl_lerpimages", "gl_anisotropy",
              "r_smoothtext", "r_smoothcrosshair", "r_smoothimages", "vid_framebuffer_smooth",
              "vid_conwidth", "vid_conheight", "vid_conscale", "r_drawparticles",
              "gl_flashblend", "r_dynamic", "r_bloom", "crosshair"}


def cvars(text):
    out = {}
    for line in text.split("\r\n"):
        parts = line.split()
        if len(parts) == 2 and not line.startswith(("//", "bind", "name")):
            out[parts[0]] = parts[1]
    return out


class UnezSquarePixelTests(unittest.TestCase):
    def setUp(self):
        self.soft = cvars(cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", {}, "soft"))
        self.gl = cvars(cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", {}, cfg.LOOK_GL))

    def test_nearest_filtering(self):
        want = {"gl_texturemode": "GL_NEAREST_MIPMAP_NEAREST",
                "gl_texturemode_viewmodels": "GL_NEAREST", "gl_lerpimages": "0",
                "gl_anisotropy": "1", "r_smoothtext": "0", "r_smoothcrosshair": "0",
                "r_smoothimages": "0", "vid_framebuffer_smooth": "0"}
        for k, v in want.items():
            self.assertEqual(self.soft.get(k), v, k)

    def test_uniform_2d_scale(self):
        self.assertEqual(self.soft["vid_conwidth"], "0")
        self.assertEqual(self.soft["vid_conheight"], "0")
        self.assertEqual(float(self.soft["vid_conscale"]) % 1, 0)

    def test_only_real_unez_cvars(self):
        block = cfg.LOOK_BLOCKS[(cfg.CLIENT_UNEZ, "soft")]
        names = {ln.split()[0] for ln in block.splitlines() if ln.strip()}
        self.assertEqual(names - UNEZ_CVARS, set())
        self.assertNotIn("gl_texturemode2d", names)  # FTE-only name
        self.assertNotIn("gl_smoothfont", names)  # legacy alias of r_smoothtext

    def test_gl_look_still_smooth(self):
        self.assertEqual(self.gl["gl_texturemode"], "GL_LINEAR_MIPMAP_LINEAR")
        self.assertNotIn("r_smoothtext", self.gl)


class CrosshairTests(unittest.TestCase):
    def test_unez_crosshair_1_both_looks(self):
        for look in ("soft", cfg.LOOK_GL):
            c = cvars(cfg.render_autoexec(cfg.CLIENT_UNEZ, "p", {}, look))
            self.assertEqual(c.get("crosshair"), "1", look)

    def test_fte_crosshair_untouched(self):
        for look in ("soft", cfg.LOOK_GL):
            t = cfg.render_autoexec(cfg.CLIENT_FTE, "p", {}, look)
            self.assertNotIn("crosshair", t)


if __name__ == "__main__":
    unittest.main()
