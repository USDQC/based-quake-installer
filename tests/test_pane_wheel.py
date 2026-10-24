import os
import unittest

from quake_installer import gui


class WheelSteps(unittest.TestCase):
    def test_linux_buttons(self):
        self.assertEqual(gui.wheel_steps(4, 0), -2)
        self.assertEqual(gui.wheel_steps(5, 0), 2)

    def test_windows_and_mac_delta(self):
        self.assertEqual(gui.wheel_steps(None, 120), -1)
        self.assertEqual(gui.wheel_steps(None, -240), 2)
        self.assertEqual(gui.wheel_steps(None, 1), -1)   # older macOS Tk
        self.assertEqual(gui.wheel_steps(None, -3), 1)
        self.assertEqual(gui.wheel_steps(None, 0), 0)

    def test_can_scroll(self):
        class C:
            def __init__(self, v):
                self.v = v

            def yview(self):
                return self.v
        self.assertFalse(gui.can_scroll(C((0.0, 1.0))))
        self.assertTrue(gui.can_scroll(C((0.0, 0.5))))
        self.assertTrue(gui.can_scroll(C((0.5, 1.0))))


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs a display")
class PaneWheel(unittest.TestCase):
    def setUp(self):
        import tempfile
        import tkinter as tk
        self.tmp = tempfile.mkdtemp()
        os.environ["XDG_CONFIG_HOME"] = self.tmp
        os.environ["APPDATA"] = self.tmp
        self.tk = tk
        self.root = tk.Tk()
        self.app = gui.InstallerApp(self.root)
        self.root.after_cancel  # keep reference
        self.root.update()

    def tearDown(self):
        import shutil
        self.root.destroy()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wheel(self, widget, down=True):
        ev = self.tk.Event()
        ev.widget, ev.num, ev.delta = widget, (5 if down else 4), 0
        return self.app._main_wheel(ev)

    def test_pane_under_cursor_scrolls_not_window(self):
        canvas = self.app._bind_canvas
        if not gui.can_scroll(canvas):
            self.skipTest("bind list fits at this size")
        child = self.app.bind_boxes[0].btn
        outer0, pane0 = self.app.main_canvas.yview(), canvas.yview()
        self.app._wheel_pane = canvas  # what <Enter> sets
        self.assertEqual(self._wheel(child), "break")
        self.root.update()
        self.assertGreater(canvas.yview()[0], pane0[0])
        self.assertEqual(self.app.main_canvas.yview(), outer0)

    def test_outside_pane_scrolls_window(self):
        self.app._wheel_pane = None
        pane0 = self.app._bind_canvas.yview()
        self._wheel(self.app.ent_root)
        self.root.update()
        self.assertEqual(self.app._bind_canvas.yview(), pane0)

    def test_capturing_box_still_takes_the_wheel(self):
        box = self.app.bind_boxes[0]
        self.app._wheel_pane = self.app._bind_canvas
        pane0 = self.app._bind_canvas.yview()
        box.start()
        ev = self.tk.Event()
        ev.delta = 120
        self.assertEqual(box._on_wheel(ev), "break")
        self.assertTrue(box.var.get())  # the wheel became the bind
        self.assertFalse(box.capturing)
        self.assertEqual(self.app._bind_canvas.yview(), pane0)


if __name__ == "__main__":
    unittest.main()
