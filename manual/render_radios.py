"""Pre-render Windows 7 style radio indicators for the Dark theme (needs Pillow).
Output: quake_installer/assets/radio/radio_<state>_<size>.png  (width = size+7)."""
import math, os
from PIL import Image

SS = 4
SIZES = (14, 16, 18, 20, 22, 24, 27, 30, 36)
OUT = os.path.join(os.path.dirname(__file__), "..", "quake_installer", "assets", "radio")

def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))

def render(size, state):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    px = img.load()
    c = n / 2.0
    R = n / 2.0 - 0.5 * SS          # outer edge
    ring_w = max(1.0, size / 9.0) * SS
    rin = R - ring_w                  # interior
    dot = R * 0.52
    dis = state == "disabled"
    hov = state == "hover"
    # ring colours: silver, top lighter
    ring_top, ring_bot = (232, 232, 232), (150, 150, 150)
    edge = (90, 90, 90)
    if hov:
        ring_top, ring_bot, edge = (215, 240, 255), (120, 185, 230), (60, 125, 190)
    if dis:
        ring_top, ring_bot, edge = (110, 110, 110), (80, 80, 80), (60, 60, 60)
    in_top, in_bot = (34, 34, 34), (72, 72, 72)   # dark sunken interior
    if hov:
        in_top, in_bot = (40, 52, 62), (70, 90, 105)
    if dis:
        in_top, in_bot = (40, 40, 40), (48, 48, 48)
    sel = state == "selected"
    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            d = math.hypot(dx, dy)
            if d > R:
                continue
            ty = (y / n)
            if d > R - SS * 0.9:
                col = edge
            elif d > rin:
                col = lerp(ring_top, ring_bot, ty)
            else:
                # interior gradient + soft inner shadow near rim
                col = lerp(in_bot, in_top, ty)  # darker at top (sunken)
                s = max(0.0, (d - rin * 0.7) / (rin * 0.3))
                col = lerp(col, (20, 20, 20), 0.35 * s * (1 - ty))
                if sel and d <= dot:
                    # glossy blue: highlight at top-left
                    hx, hy = c - dot * 0.35, c - dot * 0.4
                    t = min(1.0, math.hypot(x + 0.5 - hx, y + 0.5 - hy) / (dot * 1.35))
                    col = lerp((190, 235, 255), (28, 95, 180), t ** 0.8)
                    col = lerp(col, (10, 50, 110), max(0.0, (d - dot * 0.8) / (dot * 0.2)) * 0.6)
                    sx, sy = c - dot * 0.3, c - dot * 0.42
                    sd = math.hypot((x + 0.5 - sx) / 1.3, y + 0.5 - sy)
                    if sd < dot * 0.32:
                        col = lerp(col, (255, 255, 255), 0.85 * (1 - sd / (dot * 0.32)))
            px[x, y] = col + (255,)
    small = img.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size + 7, size), (0, 0, 0, 0))
    out.paste(small, (0, 0))
    return out

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in SIZES:
        for st in ("selected", "unselected", "hover", "disabled"):
            render(s, st).save(os.path.join(OUT, "radio_%s_%d.png" % (st, s)), optimize=True)
