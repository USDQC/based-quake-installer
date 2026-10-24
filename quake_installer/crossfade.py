"""Seamless theme switch: show a snapshot of the window on top, restyle the real
window underneath, then fade the snapshot out.

Snapshot: Windows uses GDI (ctypes, no extra packages); elsewhere Pillow's ImageGrab
if it is installed. Any failure returns None and the caller falls back to the plain
freeze/cover switch. Without a compositor (-alpha has no effect) the fade becomes a
single clean cut from the old picture to the finished new theme.
"""

import os
import tkinter as tk

IS_WINDOWS = os.name == "nt"
FADE_MS = 180
STEPS = 9
SAFETY_MS = 1500  # the overlay is always gone after this, whatever happens


def bgra_to_ppm(bgra, w, h):
    """Top-down 32-bit BGRA rows -> binary PPM (P6) bytes."""
    rgb = bytearray(w * h * 3)
    rgb[0::3] = bgra[2::4]
    rgb[1::3] = bgra[1::4]
    rgb[2::3] = bgra[0::4]
    return b"P6\n%d %d\n255\n" % (w, h) + bytes(rgb)


def _grab_windows(x, y, w, h):
    import ctypes
    from ctypes import wintypes
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    user32.GetDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.restype = ctypes.c_void_p
    for f in (gdi32.CreateCompatibleDC, gdi32.DeleteDC):
        f.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.BitBlt.argtypes = [ctypes.c_void_p] + [ctypes.c_int] * 4 + \
        [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                                wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                wintypes.UINT]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    screen = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(screen)
    bmp = gdi32.CreateCompatibleBitmap(screen, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        # SRCCOPY | CAPTUREBLT; coordinates are physical pixels (the app is DPI aware)
        if not gdi32.BitBlt(mem, 0, 0, w, h, screen, x, y, 0x00CC0020 | 0x40000000):
            return None
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth, bi.biHeight = w, -h  # negative: top-down rows
        bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.SelectObject(mem, old)
        old = None
        if gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0) != h:
            return None
        return bgra_to_ppm(buf.raw, w, h)
    finally:
        if old is not None:
            gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)


def _grab_pil(x, y, w, h):
    from PIL import ImageGrab  # optional
    kw = {} if IS_WINDOWS else {"xdisplay": os.environ.get("DISPLAY") or None}
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h), **kw).convert("RGB")
    if img.size != (w, h):
        return None
    return b"P6\n%d %d\n255\n" % (w, h) + img.tobytes()


def snapshot(root):
    """PPM bytes of the window's client area as shown now, or None."""
    try:
        root.update()  # finish pending repaints (e.g. where Settings just closed)
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
    except tk.TclError:
        return None
    if w < 2 or h < 2:
        return None
    grabbers = (_grab_windows, _grab_pil) if IS_WINDOWS else (_grab_pil,)
    for grab in grabbers:
        try:
            data = grab(x, y, w, h)
        except Exception:
            data = None
        if data:
            return data
    return None


class Crossfade:
    """Overlay showing the old look; fade() removes it smoothly. Never sticks."""

    def __init__(self, root, ppm):
        self.root = root
        self.top = None
        self._bind = None
        self.img = tk.PhotoImage(master=root, data=ppm, format="PPM")
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        top = tk.Toplevel(root)
        self.top = top
        top.withdraw()
        top.overrideredirect(True)
        try:
            top.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(top, image=self.img, borderwidth=0, highlightthickness=0,
                 takefocus=0).pack()
        self.geom = (x, y, w, h)
        top.geometry("%dx%d+%d+%d" % (w, h, x, y))
        top.deiconify()
        top.update_idletasks()
        top.update()  # the overlay is on screen before anything changes below
        # Moving/minimizing the window mid-fade: just drop the overlay.
        self._bind = root.bind("<Configure>", self._on_root_change, add="+")
        self._unmap = root.bind(
            "<Unmap>", lambda e: self.close() if e.widget is self.root else None, add="+")
        root.after(SAFETY_MS, self.close)

    def _on_root_change(self, event):
        if event.widget is not self.root:
            return
        try:
            now = (self.root.winfo_rootx(), self.root.winfo_rooty(),
                   self.root.winfo_width(), self.root.winfo_height())
        except tk.TclError:
            now = None
        if now != self.geom:  # moved or resized: the picture no longer lines up
            self.close()

    def fade(self, ms=FADE_MS, steps=STEPS):
        top = self.top
        if top is None:
            return
        try:
            top.attributes("-alpha", 1.0)
        except tk.TclError:
            self.close()  # no alpha support: clean cut
            return
        delay = max(10, ms // steps)

        def step(i):
            if self.top is None:
                return
            if i >= steps:
                self.close()
                return
            try:
                self.top.attributes("-alpha", 1.0 - float(i + 1) / steps)
            except tk.TclError:
                self.close()
                return
            self.root.after(delay, step, i + 1)

        self.root.after(delay, step, 0)

    def close(self):
        top, self.top = self.top, None
        if top is None:
            return
        for seq, fid in (("<Configure>", self._bind), ("<Unmap>", getattr(self, "_unmap", None))):
            if fid:
                try:
                    self.root.unbind(seq, fid)
                except tk.TclError:
                    pass
        try:
            top.destroy()
        except tk.TclError:
            pass
        self.img = None  # free the snapshot now, on the Tk thread


def start(root):
    """Put a snapshot overlay over root; returns a Crossfade or None (fall back)."""
    try:
        if not root.winfo_viewable() or root.state() != "normal":
            return None
    except tk.TclError:
        return None
    ppm = snapshot(root)
    if not ppm:
        return None
    try:
        return Crossfade(root, ppm)
    except Exception:
        return None
