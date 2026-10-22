"""Render the Settings (gear) button icons into quake_installer/assets/icons/.

Build-time helper, like render_radios.py: Pillow is needed only to regenerate the
PNGs, never at run time. Run from the repo root:

    python manual/render_gear.py
"""

import math
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "quake_installer", "assets", "icons")
SIZES = (18, 24, 32, 36)
COLORS = {"light": (68, 68, 68), "dark": (216, 216, 216)}
SS = 8  # supersampling factor for smooth edges


def gear_points(size, teeth=8):
    cx = cy = size / 2.0
    outer = size * 0.47
    root = size * 0.35
    tooth = 0.20   # half-width (radians) of a tooth at the outer radius
    valley = 0.16  # half-width of the flat between teeth
    step = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = i * step - math.pi / 2
        for t in range(3):
            ang = a - tooth + (2 * tooth) * t / 2.0
            pts.append((cx + outer * math.cos(ang), cy + outer * math.sin(ang)))
        b = a + step / 2
        for t in range(3):
            ang = b - valley + (2 * valley) * t / 2.0
            pts.append((cx + root * math.cos(ang), cy + root * math.sin(ang)))
    return pts


def render(size, color):
    s = size * SS
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)
    d.polygon(gear_points(s), fill=255)
    hole = s * 0.16
    d.ellipse([s / 2.0 - hole, s / 2.0 - hole, s / 2.0 + hole, s / 2.0 + hole], fill=0)
    img = Image.new("RGBA", (s, s), color + (255,))
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, color in COLORS.items():
        for size in SIZES:
            path = os.path.join(OUT, "gear-%s-%d.png" % (name, size))
            render(size, color).save(path, optimize=True)
            print(path)


if __name__ == "__main__":
    main()
