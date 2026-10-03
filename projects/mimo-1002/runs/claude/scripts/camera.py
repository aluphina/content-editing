"""Camera state per output frame: maps source pixels to output pixels as out = src / k + (ox, oy).

Modes (data.json camera.modes): full (crop by face, zoom z), split (z=1 plate slid down under the top panel),
circle (plate scaled so the face sits in the circle). Zoom changes are exponential with sine.inOut on log scale.
"""
import math, json

def sine_inout(p):
    p = min(1.0, max(0.0, p)); return -(math.cos(math.pi * p) - 1) / 2

def exp_interp(a, b, s):          # a * (b/a)^s
    return a * (b / a) ** s

class Camera:
    def __init__(self, data):
        self.d = data; P = data["project"]
        self.W, self.H, self.fps = P["width"], P["height"], P["fps"]
        self.SW, self.SH = P["src_w"], P["src_h"]
        self.cam = data["camera"]; self.segs = self.cam["segments"]
        self.k1 = self.SW / self.W                     # src px per out px at z = 1
        L = data["layout"]
        self.Ly = L["split"]["h"]; self.eye_reg = L["split"]["speaker_eye_in_region"]
        self.C = L["circle"]

    def seg_at(self, n):
        t = (n + 0.5) / self.fps
        for s in self.segs:
            if s["t0"] <= t < s["t1"]: return s
        return self.segs[-1]

    def mode_at(self, t):
        tc = t + 0.5 / self.fps                         # frame centre, same rule as seg_at
        for m in self.cam["modes"]:
            if m["t0"] <= tc < m["t1"]: return m
        return self.cam["modes"][-1]

    # --- framings -------------------------------------------------------
    def full(self, s, z):
        cw, ch = self.SW / z, self.SH / z
        x0 = min(max(s["cx"] * self.SW - cw / 2, 0), self.SW - cw)
        y0 = min(max(s["eye"] * self.SH - ch * self.cam["eye_third"], 0), self.SH - ch)
        k = self.k1 / z
        return dict(k=k, ox=-x0 / k, oy=-y0 / k)

    def split_off(self, s):
        k = self.k1
        eye_out = s["eye"] * self.SH / k
        target = self.Ly + self.eye_reg * (self.H - self.Ly) - eye_out
        top_out = s["top"] * self.SH / k
        lo = max(0.0, self.Ly - top_out + 0.012 * self.H)   # keep the top of the head below the line
        return min(max(target, lo), self.Ly - 1)

    def circle_frame(self, s):
        head_src = self.cam["head_h_src"] * self.SH
        k = head_src / (self.cam["circle_head_frac"] * 2 * self.C["r"])
        fx, fy = s["cx"] * self.SW, (s["eye"] + 0.02) * self.SH          # face centre ~ just below the eyes
        return dict(k=k, ox=self.C["cx"] - fx / k, oy=self.C["cy"] - fy / k)

    def full_zoom(self, s, t):
        z = self.cam["full_zoom"].get(str(s["i"]), 1.0)
        for p in self.cam["push"]:
            if p["seg"] == s["i"]:
                if t <= p["t0"]: z = p["z0"]
                elif t >= p["t1"]: z = p["z1"]
                else: z = exp_interp(p["z0"], p["z1"], sine_inout((t - p["t0"]) / (p["t1"] - p["t0"])))
        return z

    # --- state ----------------------------------------------------------
    def state(self, n):
        t = n / self.fps; s = self.seg_at(n); m = self.mode_at(t)
        st = dict(n=n, t=t, seg=s["i"], mode=m["mode"], line=None, hole=None)
        if m["mode"] == "full":
            st.update(self.full(s, self.full_zoom(s, t)))
        elif m["mode"] == "split":
            p = 1.0 if not m.get("open") else sine_inout((t - m["open"][0]) / (m["open"][1] - m["open"][0]))
            f = self.full(s, 1.0)
            st.update(k=f["k"], ox=f["ox"], oy=f["oy"] + p * self.split_off(s), line=p * self.Ly)
        else:  # circle
            a = self.full(s, 1.0); b = self.circle_frame(s)
            sh, ex = m["shrink"], m["expand"]
            if t < sh[1]: q = sine_inout((t - sh[0]) / (sh[1] - sh[0]))
            elif t >= ex[0]: q = 1 - sine_inout((t - ex[0]) / (ex[1] - ex[0]))
            else: q = 1.0
            hole = exp_interp(self.C["R0"], self.C["r"], q)
            pb = (self.C["cx"], self.C["cy"])
            def face_full(sg):
                f = self.full(sg, 1.0)
                return (sg["cx"] * self.SW / f["k"] + f["ox"], (sg["eye"] + 0.02) * self.SH / f["k"] + f["oy"])
            # the hole centre travels from the face (in the full frame) to its final place, on the same curve
            ref = self.seg_at(round(m["t0"] * self.fps)) if t < sh[1] else self.seg_at(round(m["t1"] * self.fps) - 1)
            rf = face_full(ref)
            hx, hy = rf[0] + (pb[0] - rf[0]) * q, rf[1] + (pb[1] - rf[1]) * q
            vx0, vx1 = max(0.0, hx - hole), min(float(self.W), hx + hole)
            vy0, vy1 = max(0.0, hy - hole), min(float(self.H), hy + hole)
            k = exp_interp(a["k"], b["k"], q)
            k = max(min(k, self.SW / (vx1 - vx0), self.SH / (vy1 - vy0)), a["k"])
            fx, fy = s["cx"] * self.SW, (s["eye"] + 0.02) * self.SH
            pa = face_full(s)
            px, py = pa[0] + (pb[0] - pa[0]) * q, pa[1] + (pb[1] - pa[1]) * q
            ox, oy = px - fx / k, py - fy / k
            ox = min(max(ox, vx1 - self.SW / k), vx0)
            oy = min(max(oy, vy1 - self.SH / k), vy0)
            st.update(k=k, ox=ox, oy=oy, hole=hole, hole_c=[hx, hy])
        return st

if __name__ == "__main__":
    import sys
    d = json.load(open(sys.argv[1])); cam = Camera(d)
    N = round(d["duration"] * cam.fps)
    rows = [cam.state(n) for n in range(N)]
    json.dump(rows, open(sys.argv[2], "w"))
    print(N, "frames")
