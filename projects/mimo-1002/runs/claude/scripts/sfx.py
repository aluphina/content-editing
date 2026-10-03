"""Whooshes synthesised from filtered noise (the user asked for them; no sfx/ folder exists),
their measured catalogue (edit/sfx_catalog.json) and the voice+sfx mix with loudness normalisation."""
import json, sys, os, wave, subprocess, numpy as np

SR = 48000

def whoosh(length, peak_frac, rise, seed):
    rng = np.random.default_rng(seed)
    n = int(length * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    # sweep a resonant band-pass: centre moves low->high (or high->low) through the peak
    p = t / length
    f = 180 * (14 ** p) if rise else 2500 * (1 / 14) ** p
    y = np.zeros(n); bp1 = bp2 = 0.0
    for i in range(n):               # state-variable filter, cheap enough for < 1 s
        fc = 2 * np.sin(np.pi * min(f[i], 9000) / SR); q = 0.55
        hp = noise[i] - bp1 * q - bp2
        bp1 += fc * hp; bp2 += fc * bp1
        y[i] = bp1
    # envelope: smooth swell to the peak, faster decay; peak at peak_frac
    env = np.where(p < peak_frac, (p / peak_frac) ** 2.2, np.exp(-((p - peak_frac) / (1 - peak_frac)) * 4.5))
    y *= env
    a = np.exp(-2 * np.pi * 4500 / SR); lp = np.zeros(n); z = 0.0      # gentle one-pole low-pass: no hiss
    for i in range(n): z = (1 - a) * y[i] + a * z; lp[i] = z
    y = lp / (np.abs(lp).max() + 1e-9)
    return y.astype(np.float32)

def measure(y):
    n = len(y); env = np.sqrt(np.convolve(y ** 2, np.ones(480) / 480, "same"))
    spec = np.abs(np.fft.rfft(y)); fr = np.fft.rfftfreq(n, 1 / SR)
    return {"duration": round(n / SR, 3), "peak_t": round(int(np.argmax(env)) / SR, 3),
            "rms_db": round(float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9)), 1),
            "centroid_hz": round(float((spec * fr).sum() / spec.sum())), "shape": "swell-to-peak + decay (whoosh)",
            "type": "whoosh", "use": "split/circle transitions, push-ins, element landings"}

def load(path):
    w = wave.open(path); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x, w.getframerate()

def main(data_json, voice_wav, out_wav, catalog_json):
    d = json.load(open(data_json)); voice, sr = load(voice_wav); assert sr == SR
    mix = voice.copy() * d["mix"]["voice"]
    cat = []
    for k, s in enumerate(d["sfx"]):
        pf = 0.62 if s["rise"] else 0.45
        y = whoosh(s["len"], pf, s["rise"], seed=k + 7)
        m = measure(y)
        start = int((s["peak"] - m["peak_t"]) * SR)
        a, b = max(0, start), min(len(mix), start + len(y))
        mix[a:b] += y[a - start:b - start] * s["gain"]
        cat.append({"id": f"whoosh_{k:02d}", "at_peak": s["peak"], "gain_linear": s["gain"], **m})
    tmp = out_wav + ".pre.wav"
    w = wave.open(tmp, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
    # two-pass loudnorm to target on the final mix
    tgt = d["mix"]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", f"loudnorm=I={tgt['target_lufs']}:TP={tgt['true_peak']}:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    js = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    af = (f"loudnorm=I={tgt['target_lufs']}:TP={tgt['true_peak']}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,aresample={SR}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", af, "-ac", "2", "-c:a", "pcm_s16le", out_wav], check=True)
    os.remove(tmp)
    json.dump(cat, open(catalog_json, "w"), ensure_ascii=False, indent=1)
    print(len(cat), "whooshes;", "pre-norm", js["input_i"], "LUFS")

if __name__ == "__main__":
    main(*sys.argv[1:5])
