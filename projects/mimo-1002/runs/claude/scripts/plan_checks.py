"""Write edit/graphics_plan.md and run the non-render checks: camera speeds/amplitudes, split line vs head,
event density and overlap of big elements. Results -> edit/checks/plan_checks.json."""
import json, sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from camera import Camera

E = "edit"
d = json.load(open(f"{E}/data.json")); words = json.load(open(f"{E}/words.json"))["words"]
cam = Camera(d); st = json.load(open(f"{E}/camera_states.json")); track = json.load(open(f"{E}/track.json"))
fps = d["project"]["fps"]; H = d["project"]["height"]; W = d["project"]["width"]
res = {}

# ---- camera: pushes
pushes = []
for p in d["camera"]["push"]:
    n0, n1 = math.ceil(p["t0"] * fps), math.floor(p["t1"] * fps)
    z = [cam.k1 / st[n]["k"] for n in range(n0 - 1, n1 + 2)]
    rate = [abs(z[i + 1] / z[i] - 1) * 100 for i in range(len(z) - 1)]
    acc = [abs(rate[i + 1] - rate[i]) for i in range(len(rate) - 1)]
    pushes.append({"seg": p["seg"], "amplitude_pct": round((p["z1"] / p["z0"] - 1) * 100, 1), "peak_pct_per_frame": round(max(rate), 3),
                   "max_rate_step": round(max(acc), 4), "within_one_segment": cam.seg_at(n0)["i"] == cam.seg_at(n1)["i"],
                   "ok": (p["z1"] / p["z0"] - 1) >= 0.30 and max(rate) <= 1.2 * 25 / fps})
res["push"] = pushes
# ---- split: shift speed (vertical, % of frame height per frame) and head top below the line on every frame
sp = []
for m in d["camera"]["modes"]:
    if m["mode"] != "split": continue
    if m.get("open"):
        n0, n1 = math.floor(m["open"][0] * fps), math.ceil(m["open"][1] * fps)
        dy = [abs(st[n + 1]["oy"] - st[n]["oy"]) / H * 100 for n in range(n0, n1)]
        dl = [abs((st[n + 1]["line"] or 0) - (st[n]["line"] or 0)) / H * 100 for n in range(n0, n1)]
        sp.append({"open": m["open"], "peak_shift_pct_h_per_frame": round(max(dy), 2), "peak_line_pct_h_per_frame": round(max(dl), 2),
                   "duration": round(m["open"][1] - m["open"][0], 2)})
viol = []
for n, s in enumerate(st):
    if s["mode"] == "split" and s["line"] and track[n]:
        head_top = track[n]["top"] * cam.SH / s["k"] + s["oy"]
        if head_top < s["line"] - 1: viol.append((n, round(head_top - s["line"], 1)))
res["split"] = {"opens": sp, "frames_line_over_head": len(viol), "worst": sorted(viol, key=lambda v: v[1])[:5]}
# ---- full-frame cuts: scale difference across cuts in full mode
cuts = []
for s in d["camera"]["segments"][1:]:
    n = round(s["t0"] * fps); a, b = st[n - 1], st[n]
    if a["mode"] == b["mode"] == "full":
        cuts.append({"t": s["t0"], "z_before": round(cam.k1 / a["k"], 3), "z_after": round(cam.k1 / b["k"], 3),
                     "diff_pct": round(abs(a["k"] / b["k"] - 1) * 100, 1)})
res["full_cuts"] = cuts

# ---- events & density
EV = []   # (t, label, big)
for g in d["graphics"]:
    k = g["kind"]
    EV.append((g["t0"], f"{k} in", True))
    for key in ("cards", "lines", "steps", "items", "files"):
        for x in [y for y in g.get(key, []) if isinstance(y, dict)]:
            EV.append((x["t"], f"{k}: {x.get('title') or x.get('text')}", False))
            for c in x.get("chips", []): EV.append((c["t"], f"{k} chip: {c['text']}", False))
    for key in ("check_t", "strike_t", "vs_t", "folder_t"):
        if key in g: EV.append((g[key], f"{k} {key[:-2]}", False))
    if k == "hook":
        for row, ts in zip(g["lines"], g["word_t"]):
            for w_, t_ in zip(row, ts): EV.append((t_, f"hook word: {w_}", False))
    if k == "slide": EV.append((g["no"]["t"], "slide: НЕ-card", False)); EV.append((g["no"]["strike_t"], "slide: strike", False))
for p in d["camera"]["push"]: EV.append((p["t0"], "push-in", True))
for m in d["camera"]["modes"]:
    if m["mode"] == "circle": EV += [(m["shrink"][0], "circle shrink", True), (m["expand"][0], "circle expand", True)]
    if m["mode"] == "split" and m.get("open"): EV.append((m["open"][0], "split opens", True))
EV.sort()
gaps = [(round(EV[i + 1][0] - EV[i][0], 2), EV[i][0], EV[i][1]) for i in range(len(EV) - 1)]
res["density"] = {"events": len(EV), "max_gap": max(gaps), "mean_gap": round((EV[-1][0] - EV[0][0]) / (len(EV) - 1), 2),
                  "gaps_over_4s": [g for g in gaps if g[0] > 4]}

# ---- graphics plan
def wtxt(t):
    near = min(words, key=lambda w: abs(w["t0"] - (t + d["project"]["lead"])))
    return near["w"]
with open(f"{E}/graphics_plan.md", "w") as f:
    f.write("# План графики\n\nВремя — секунды смонтированного ролика. Появление = атака слова минус опережение 0,1 с.\n\n")
    f.write("| время | слова | элемент | что анимируется | звук |\n|---|---|---|---|---|\n")
    sfx = d["sfx"]
    for t, lab, big in EV:
        s = next((x for x in sfx if abs(x["peak"] - t - 0.3) < 0.7 or abs(x["peak"] - t) < 0.7), None)
        f.write(f"| {t:.2f} | {wtxt(t)} | {'**' + lab + '**' if big else lab} | "
                f"{'вход 0.85→1.04→1, expo.out' if big else 'часть элемента: печать/галочка/пункт'} | {'свуш' if s else '—'} |\n")
json.dump(res, open(f"{E}/checks/plan_checks.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
