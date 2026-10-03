"""Checks on the delivered file (out/final.mp4) against the lossless references. -> edit/checks/final_checks.json"""
import json, subprocess, sys, os, difflib, re, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load

E, OUT = "edit", "out/final.mp4"
d = json.load(open(f"{E}/data.json")); fps = d["project"]["fps"]; W, H = d["project"]["width"], d["project"]["height"]
res = {}
ACC = "accurate_rnd+full_chroma_int+full_chroma_inp"

def frame(src, n, concat=False, fmt="rgb24"):
    args = ["ffmpeg", "-v", "error"] + (["-f", "concat", "-safe", "0"] if concat else []) + ["-i", src, "-vf",
            f"select=eq(n\\,{n}),scale=in_range=auto:out_range=pc:flags={ACC},format={fmt}", "-frames:v", "1", "-f", "rawvideo", "-"]
    b = subprocess.run(args, capture_output=True).stdout
    return np.frombuffer(b, np.uint8).reshape(H, W, -1)

# ---- file
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=codec_name,width,height,r_frame_rate,"
                                "pix_fmt,color_range,color_space,color_primaries,color_transfer,nb_frames", "-of", "json", OUT],
                               capture_output=True, text=True).stdout)
res["file"] = {"format": pr["format"], "video": pr["streams"][0], "audio": pr["streams"][1]["codec_name"]}

# ---- loudness
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", OUT, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
summ = r[r.rindex("Summary:"):]
res["loudness"] = {"I_LUFS": float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1)),
                   "true_peak_dBFS": float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))}

# ---- sync: final audio vs the mix that went in (cross-correlation)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", OUT, "-ac", "1", "-ar", "48000", f"{E}/checks/final_audio.wav"], check=True)
a, _ = load(f"{E}/checks/final_audio.wav"); m, _ = load(f"{E}/audio/mix.wav") if False else (None, None)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{E}/audio/mix.wav", "-ac", "1", f"{E}/checks/mix_mono.wav"], check=True)
b, _ = load(f"{E}/checks/mix_mono.wav")
seg = slice(48000 * 10, 48000 * 40)
x, y = a[seg], b[seg]
N = 1 << int(np.ceil(np.log2(len(x) * 2)))
cc = np.fft.irfft(np.fft.rfft(x, N) * np.conj(np.fft.rfft(y, N)), N)
lag = int(np.argmax(np.concatenate([cc[-4800:], cc[:4801]]))) - 4800
res["sync_ms"] = round(lag / 48, 2)

# ---- completeness: transcribe the delivered audio and compare with the selected phrases
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{E}/checks/final_audio.wav", "-ar", "16000", f"{E}/checks/final16.wav"], check=True)
txt = subprocess.run(["whisper-cli", "-m", os.path.expanduser("~/models/ggml-large-v3-turbo.bin"), "-l", "ru", "-t", "4", "-nt", "-np",
                      f"{E}/checks/final16.wav"], capture_output=True, text=True).stdout
norm = lambda s: re.sub(r"[^\w\s-]", " ", s.lower().replace("ё", "е")).split()
ref = norm(" ".join(p["text"] for p in json.load(open(f"{E}/edl.json"))["phrases"]))
got = norm(txt)
sm = difflib.SequenceMatcher(a=ref, b=got)
res["speech"] = {"ratio": round(sm.ratio(), 3), "ref_words": len(ref), "heard_words": len(got),
                 "diffs": [(op, " ".join(ref[i1:i2]), " ".join(got[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]}

# ---- levels & sharpness vs the lossless plate, on frames with no graphics over the speaker area
st = json.load(open(f"{E}/camera_states.json"))
lv = []; sh = []
for n in (5, 200, 560, 1270, 1500, 1800):
    f_ = frame(OUT, n).astype(np.float32); p_ = frame(f"{E}/plate/concat.txt", n, concat=True).astype(np.float32)
    s = st[n]
    y0 = int(s["line"] + 10) if s.get("line") else 0
    y1 = int(0.78 * H)                       # above the subtitle band
    lum = lambda z: 0.2126 * z[..., 0] + 0.7152 * z[..., 1] + 0.0722 * z[..., 2]
    A, B = lum(f_[y0:y1]), lum(p_[y0:y1])
    lv.append({"n": n, "mode": s["mode"], "final_p1_50_99": [round(float(np.percentile(A, q)), 1) for q in (1, 50, 99)],
               "plate_p1_50_99": [round(float(np.percentile(B, q)), 1) for q in (1, 50, 99)],
               "clip0_pct": round(float((f_[y0:y1] <= 0).any(-1).mean()) * 100, 3), "clip255_pct": round(float((f_[y0:y1] >= 255).any(-1).mean()) * 100, 3)})
    def lapvar(z):
        z = z[1:-1, 1:-1] * 4 - z[:-2, 1:-1] - z[2:, 1:-1] - z[1:-1, :-2] - z[1:-1, 2:]; return float(z.var())
    # face crop around the tracked face
    tr = json.load(open(f"{E}/track.json"))[n]
    if tr:
        cx = tr["cx"] * 1728 / s["k"] + s["ox"]; cy = (tr["eye_y"] + 0.03) * 3072 / s["k"] + s["oy"]
        r = int(0.12 * W)
        ys, xs = slice(max(0, int(cy - r)), min(H, int(cy + r))), slice(max(0, int(cx - r)), min(W, int(cx + r)))
        sh.append({"n": n, "lapvar_ratio_final_vs_plate": round(lapvar(lum(f_[ys, xs])) / lapvar(lum(p_[ys, xs])), 3)})
res["levels"] = lv; res["sharpness_face"] = sh

# ---- subtitle timing from the front layer alpha: first visible frame vs planned start
fr = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{E}/comp/front.mov", "-vf",
                     f"crop={int(0.8*W)}:{int(0.07*H)}:{int(0.1*W)}:{int(d['layout']['subtitle_y']-0.035*H)},format=yuva444p,alphaextract,scale=108:20",
                     "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
al = np.frombuffer(fr, np.uint8).reshape(-1, 20, 108)
errs = []
for s in d["subtitles"]["items"][1:]:
    n0 = round(s["t0"] * fps)
    win = al[max(0, n0 - 3): n0 + 4]
    # change of the subtitle band between consecutive frames marks the swap
    diffs = [np.abs(win[i + 1].astype(int) - win[i].astype(int)).mean() for i in range(len(win) - 1)]
    k = int(np.argmax(diffs)) + max(0, n0 - 3) + 1
    errs.append(k - n0)
res["subtitle_swap_frame_error"] = {"n": len(errs), "within_1_frame": int(sum(abs(e) <= 1 for e in errs)), "max_abs": int(max(abs(e) for e in errs))}
json.dump(res, open(f"{E}/checks/final_checks.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
