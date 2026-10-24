import os
import unittest
from unittest import mock

from quake_installer import crossfade


class Ppm(unittest.TestCase):
    def test_bgra_to_ppm(self):
        bgra = bytes([1, 2, 3, 255, 10, 20, 30, 255])  # two pixels, BGRA
        ppm = crossfade.bgra_to_ppm(bgra, 2, 1)
        self.assertEqual(ppm, b"P6\n2 1\n255\n" + bytes([3, 2, 1, 30, 20, 10]))


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs a display")
class Overlay(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.geometry("200x120+50+60")
        self.root.update()
        self.ppm = crossfade.bgra_to_ppm(bytes([40, 40, 40, 255]) * (200 * 120), 200, 120)

    def tearDown(self):
        import gc
        gc.collect()  # Tk images must be freed on this thread, before the root goes
        self.root.destroy()
        gc.collect()

    def _tops(self):
        return [w for w in self.root.winfo_children() if isinstance(w, self.tk.Toplevel)]

    def test_snapshot_failure_falls_back(self):
        with mock.patch.object(crossfade, "snapshot", return_value=None):
            self.assertIsNone(crossfade.start(self.root))

    def test_withdrawn_window_falls_back(self):
        self.root.withdraw()
        with mock.patch.object(crossfade, "snapshot", return_value=self.ppm) as snap:
            self.assertIsNone(crossfade.start(self.root))
            snap.assert_not_called()

    def test_overlay_matches_window_and_fades_away(self):
        with mock.patch.object(crossfade, "snapshot", return_value=self.ppm):
            cf = crossfade.start(self.root)
        self.assertIsNotNone(cf)
        top = cf.top
        self.assertEqual((top.winfo_width(), top.winfo_height()), (200, 120))
        cf.fade(ms=40, steps=4)
        for _ in range(50):
            self.root.update()
            self.root.after(10)
            if cf.top is None:
                break
        self.assertIsNone(cf.top)
        self.assertEqual(self._tops(), [])

    def test_no_alpha_is_a_clean_cut(self):
        cf = crossfade.Crossfade(self.root, self.ppm)
        real = cf.top.attributes

        def attrs(*a):
            if a and a[0] == "-alpha":
                raise self.tk.TclError("no alpha")
            return real(*a)
        cf.top.attributes = attrs
        cf.fade()
        self.assertIsNone(cf.top)

    def test_moving_the_window_drops_the_overlay(self):
        cf = crossfade.Crossfade(self.root, self.ppm)
        self.root.geometry("200x120+90+90")
        for _ in range(20):
            self.root.update()
            if cf.top is None:
                break
        self.assertIsNone(cf.top)

    def test_child_configure_does_not_drop_it(self):
        lbl = self.tk.Label(self.root, text="x")
        cf = crossfade.Crossfade(self.root, self.ppm)
        lbl.pack()
        lbl.pack_forget()
        self.root.update()
        self.assertIsNotNone(cf.top)
        cf.close()

    def test_safety_timeout(self):
        with mock.patch.object(crossfade, "SAFETY_MS", 30):
            cf = crossfade.Crossfade(self.root, self.ppm)
        for _ in range(30):
            self.root.update()
            self.root.after(10)
            if cf.top is None:
                break
        self.assertIsNone(cf.top)


if __name__ == "__main__":
    unittest.main()
