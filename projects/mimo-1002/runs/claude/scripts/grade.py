"""Primary grade on display-referred BT.709 RGB float (0..1): levels + warm autumn look. Params come from data.json."""
import numpy as np

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def apply(rgb, g):
    """rgb: float32 HxWx3 in 0..1 (full range). g: dict from data.json['grade']."""
    x = rgb
    # 1. levels: black/white point (in 0..255 of input) -> targets
    bi, wi = g["black_in"] / 255, g["white_in"] / 255
    bo, wo = g["black_out"] / 255, g["white_out"] / 255
    x = (x - bi) / (wi - bi)
    # 2. gentle S-curve around mid (contrast), midtone gamma
    x = np.clip(x, 0, 1) ** g["gamma"]
    c = g["contrast"]
    x = x + c * (x - 0.5) * (1 - np.abs(2 * x - 1))           # soft S, endpoints fixed
    y = 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]
    # 3. split toning: warm shadows (brown), golden highlights
    sh = (1 - smoothstep(0.0, 0.55, y))[..., None]
    hi = smoothstep(0.45, 1.0, y)[..., None]
    x = x + sh * np.array(g["shadow_tint"]) + hi * np.array(g["highlight_tint"])
    # 4. global warmth (white balance gains)
    gain = np.array(g["wb_gain"]); x = x * (gain / gain.max())   # warm by pulling G/B down, never pushing R past white
    # 5. autumn hue work: greens -> olive/yellow, blues/cyans desaturated
    r, gg, b = x[..., 0], x[..., 1], x[..., 2]
    mx = x.max(-1); mn = x.min(-1); sat = mx - mn
    green = np.clip((gg - np.maximum(r, b)) / (sat + 1e-4), 0, 1) * smoothstep(0.02, 0.15, sat)
    blue = np.clip((b - np.maximum(r, gg)) / (sat + 1e-4), 0, 1) * smoothstep(0.02, 0.15, sat)
    x[..., 0] += green * sat * g["green_to_olive"]            # push greens toward yellow-olive
    x[..., 2] -= green * sat * g["green_to_olive"] * 0.5
    yy = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x = yy + (x - yy) * (1 - blue[..., None] * g["blue_desat"])
    # 6. overall saturation
    yy = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x = yy + (x - yy) * g["saturation"]
    # soft highlight roll-off per channel (no hard clip of skin/lamp)
    k = g.get("rolloff_knee", 0.88)
    x = np.where(x > k, k + (1 - k) * np.tanh((x - k) / (1 - k)), x)
    # soft toe: warm tint must not crush any channel to pure 0
    t = g.get("toe", 0.03)
    x = np.where(x < t, t * np.exp((x - t) / t), x)
    # output range
    return np.clip(bo + x * (wo - bo), 0, 1)
