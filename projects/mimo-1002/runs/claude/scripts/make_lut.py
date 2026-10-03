"""Bake the grade (data.json['grade']) into a 65^3 .cube LUT applied by ffmpeg in 16-bit before resampling."""
import json, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import grade
def main(data_json, out, n=65):
    g = json.load(open(data_json))["grade"]
    v = np.linspace(0, 1, n, dtype=np.float64)
    b, gg, r = np.meshgrid(v, v, v, indexing="ij")          # .cube: R changes fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 1, 3)
    # grade switched off on request: identity LUT (only the HDR->SDR conversion remains)
    o = (grade.apply(rgb.copy(), g) if g.get("enabled", True) else rgb.copy()).reshape(-1, 3)
    with open(out, "w") as f:
        f.write(f"TITLE \"autumn warm\"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        np.savetxt(f, o, fmt="%.6f")
if __name__ == "__main__": main(*sys.argv[1:3])
