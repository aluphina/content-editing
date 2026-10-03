"""Measure text with the real font files (variable weight), incl. letter-spacing and browser safety margin."""
from PIL import ImageFont
import os

FONTS = {"accent": os.path.expanduser("~/fonts/Unbounded[wght].ttf"),
         "text": os.path.expanduser("~/fonts/Onest[wght].ttf")}
BROWSER_PAD = {"accent": 1.025, "text": 1.01}   # browsers draw ~2.5 % / 1 % wider than PIL
_cache = {}

def font(kind, size, weight):
    k = (kind, round(size, 2), weight)
    if k not in _cache:
        f = ImageFont.truetype(FONTS[kind], max(1, int(round(size))))
        f.set_variation_by_axes([weight]); _cache[k] = f
    return _cache[k]

def width(text, kind, size, weight, tracking_em=0.0):
    f = font(kind, size, weight)
    w = f.getlength(text) * size / max(1, int(round(size)))
    w += tracking_em * size * max(0, len(text) - 1)
    return w * BROWSER_PAD[kind]

def fit_one_line(text, kind, size, weight, max_w, min_scale, tracking_em=0.0):
    """Shrink to fit one line, down to size*min_scale. Returns (size, fits)."""
    s = size
    while width(text, kind, s, weight, tracking_em) > max_w and s > size * min_scale:
        s -= 0.5
    return s, width(text, kind, s, weight, tracking_em) <= max_w

def balanced_break(text, kind, size, weight, max_w, tracking_em=0.0):
    """Two lines with the shortest possible longer line."""
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        m = max(width(a, kind, size, weight, tracking_em), width(b, kind, size, weight, tracking_em))
        if best is None or m < best[0]: best = (m, [a, b])
    return best[1] if best and best[0] <= max_w else None

def missing_glyphs(text, kind):
    f = font(kind, 64, 400)
    nd = bytes(f.getmask("￿"))
    return sorted({c for c in text if not c.isspace() and bytes(f.getmask(c)) == nd})
