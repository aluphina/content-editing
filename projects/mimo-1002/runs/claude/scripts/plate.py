"""Render the background plate (speaker with all camera moves) straight from the 10-bit source.

One resampling pass (PIL LANCZOS with a float box = sub-pixel), grade baked in a 16-bit LUT before it.
Chunks are cached per EDL segment; the key covers source range, camera states and grade.
"""
import json, sys, os, hashlib, subprocess, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from camera import Camera

def render_frame(img, st, W, H):
    out = Image.new("RGB", (W, H))
    k, ox, oy = st["k"], st["ox"], st["oy"]
    SW, SH = img.size
    # output region covered by the source footprint
    x0 = max(0, int(np.ceil(ox))); y0 = max(0, int(np.ceil(oy)))
    x1 = min(W, int(np.floor(ox + SW / k))); y1 = min(H, int(np.floor(oy + SH / k)))
    if st["mode"] == "split" and st["line"] is not None: y0 = max(y0, int(np.floor(st["line"])))
    if st["mode"] == "circle" and st["hole"] is not None:
        hx, hy = st["hole_c"]; r = st["hole"] + 2
        x0 = max(x0, int(hx - r)); x1 = min(x1, int(hx + r) + 1)
        y0 = max(y0, int(hy - r)); y1 = min(y1, int(hy + r) + 1)
    if x1 <= x0 or y1 <= y0: return out
    box = ((x0 - ox) * k, (y0 - oy) * k, (x1 - ox) * k, (y1 - oy) * k)
    box = (max(0.0, box[0]), max(0.0, box[1]), min(float(SW), box[2]), min(float(SH), box[3]))
    out.paste(img.resize((x1 - x0, y1 - y0), Image.LANCZOS, box=box), (x0, y0))
    return out

def main(data_json, edl_json, src, lut, outdir):
    d = json.load(open(data_json)); cam = Camera(d); segs = json.load(open(edl_json))["segments"]
    W, H, SW, SH = cam.W, cam.H, cam.SW, cam.SH
    os.makedirs(outdir, exist_ok=True)
    lut_hash = hashlib.md5(open(lut, "rb").read()).hexdigest()[:8]
    n0 = 0; listing = []
    for i, s in enumerate(segs):
        nfr = s["f_out"] - s["f_in"]
        states = [cam.state(n) for n in range(n0, n0 + nfr)]
        for st in states: st["_circle"] = cam.C
        key = hashlib.md5(json.dumps([s["f_in"], s["f_out"], [(round(a["k"], 6), round(a["ox"], 4), round(a["oy"], 4), a["line"], a["hole"], a.get("hole_c")) for a in states],
                                      lut_hash, d["tonemap"]]).encode()).hexdigest()[:12]
        out = f"{outdir}/seg{i:02d}_{key}.mkv"; listing.append(out)
        if not os.path.exists(out):
            vf = f"select='between(n,{s['f_in']},{s['f_out']-1})',{d['tonemap']},lut3d=file={lut}:interp=tetrahedral,format=rgb24"
            dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", vf, "-sws_flags", "accurate_rnd+full_chroma_int",
                                    "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=SW * SH * 3)
            enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(cam.fps),
                                    "-i", "-", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "gbrp", "-color_range", "pc", out + ".tmp.mkv"],
                                   stdin=subprocess.PIPE)
            for st in states:
                buf = dec.stdout.read(SW * SH * 3)
                assert len(buf) == SW * SH * 3, f"short read seg {i}"
                img = Image.frombuffer("RGB", (SW, SH), buf, "raw", "RGB", 0, 1)
                enc.stdin.write(render_frame(img, st, W, H).tobytes())
            dec.stdout.close(); dec.wait(); enc.stdin.close(); enc.wait()
            os.rename(out + ".tmp.mkv", out)
            print(f"seg {i:02d}: {nfr} frames -> {os.path.basename(out)}", flush=True)
        n0 += nfr
    with open(f"{outdir}/concat.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in listing)
    # drop stale chunks
    for fn in os.listdir(outdir):
        p = os.path.join(outdir, fn)
        if fn.startswith("seg") and p not in listing and fn.endswith(".mkv"): os.remove(p)

if __name__ == "__main__":
    main(*sys.argv[1:6])
