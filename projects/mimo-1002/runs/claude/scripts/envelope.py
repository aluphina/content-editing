"""RMS envelope (10 ms window, 5 ms hop) in dB re 98th percentile, plus pause detection."""
import numpy as np, wave, json, sys

def load(path):
    w = wave.open(path); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x, sr

def envelope(x, sr, win=0.010, hop=0.005):
    n, h = int(sr*win), int(sr*hop)
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::h]
    rms = np.sqrt((frames**2).mean(1) + 1e-12)
    db = 20*np.log10(rms)
    return db - np.percentile(db, 98), hop

def pauses(db, hop, thr, min_len):
    low = db < thr; out = []; i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]: j += 1
            if (j-i)*hop >= min_len: out.append((i*hop, j*hop))
            i = j
        else: i += 1
    return out

if __name__ == "__main__":
    x, sr = load(sys.argv[1]); db, hop = envelope(x, sr)
    print("percentiles 5/20/50/80:", [round(float(np.percentile(db,p)),1) for p in (5,20,50,80)])
    for thr in (-30,-26,-22):
        ps = pauses(db, hop, thr, 0.7); print(thr, len(ps), [(round(a,2),round(b,2)) for a,b in ps[:40]])

def islands(db, hop, thr=-15, merge=0.15, min_len=0.06):
    on = db > thr; out = []; i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]: j += 1
            out.append([i*hop, j*hop]); i = j
        else: i += 1
    m = []
    for a, b in out:
        if m and a - m[-1][1] < merge: m[-1][1] = b
        else: m.append([a, b])
    return [(a, b) for a, b in m if b - a >= min_len]
