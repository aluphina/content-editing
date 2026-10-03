"""Snap word starts to physical attacks in the waveform (section 5 of the brief).

Attacks: A - rise above thr_a after >=20 ms below; B - rise >=8 dB within 40 ms inside speech;
P - end of a pause >=150 ms (pause = below noise+12 dB, dips <80 ms do not break it).
Global model offset is found by brute force; words and attacks are matched in order (DP),
one attack per word, window +-150 ms (+-450 ms for P), quadratic cost.
"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load, envelope

def detect_attacks(db, hop, noise=None):
    if noise is None: noise = float(np.percentile(db, 10))
    thr_a = max(-20.0, noise + 8)            # noisy room: -20 dB sits in the noise, so noise+8
    thr_p = noise + 12
    att = []
    below = 0
    for i in range(1, len(db)):
        if db[i-1] < thr_a: below += 1
        else:
            if below * hop >= 0.020 and db[i] >= thr_a: att.append((i*hop, "A"))
            below = 0 if db[i] >= thr_a else below
        if db[i] < thr_a: continue
    k = int(0.040 / hop)
    last_b = -1
    for i in range(k, len(db)):
        if db[i] > thr_a + 6 and db[i] - db[i-k:i].min() >= 8 and (i - last_b) * hop > 0.12:
            att.append(((i - k + int(np.argmin(db[i-k:i]))) * hop + hop, "B")); last_b = i
    # pauses: below thr_p, bridging non-pause blips shorter than 80 ms
    low = db < thr_p
    runs, i = [], 0
    while i < len(low):
        j = i
        while j < len(low) and low[j] == low[i]: j += 1
        runs.append([low[i], i, j]); i = j
    for r in runs:
        if not r[0] and (r[2] - r[1]) * hop < 0.080: r[0] = True
    merged = []
    for r in runs:
        if merged and merged[-1][0] == r[0]: merged[-1][2] = r[2]
        else: merged.append(list(r))
    for r in merged:
        if r[0] and (r[2] - r[1]) * hop >= 0.150 and r[2] < len(db): att.append((r[2]*hop, "P"))
    att.sort()
    out = []
    pri = {"P": 0, "A": 1, "B": 2}
    for t, kind in att:
        if out and t - out[-1][0] < 0.04:
            if pri[kind] < pri[out[-1][1]]: out[-1] = (t, kind)
            continue
        out.append((t, kind))
    return out, dict(noise=noise, thr_a=thr_a, thr_p=thr_p)

TYPE_COST = {"P": 0.0, "A": 0.1, "B": 0.45}

def match(word_t, att, shift, w=0.150, wp=0.450, miss=1.0):
    """Ordered DP: returns (cost, assignment list of attack idx or -1)."""
    n, m = len(word_t), len(att)
    at = np.array([a[0] for a in att]); ap = np.array([a[1] == "P" for a in att])
    INF = 1e18
    cost = np.full((n + 1, m + 1), INF); cost[0, :] = 0
    back = np.zeros((n + 1, m + 1), np.int8)  # 0: skip attack, 1: word unmatched, 2: match
    for i in range(1, n + 1):
        t = word_t[i-1] + shift
        cost[i, 0] = cost[i-1, 0] + miss; back[i, 0] = 1
        for j in range(1, m + 1):
            best, b = cost[i, j-1], 0
            c1 = cost[i-1, j] + miss
            if c1 < best: best, b = c1, 1
            d = at[j-1] - t; win = wp if ap[j-1] else w
            if abs(d) <= win:
                c2 = cost[i-1, j-1] + (d / win) ** 2 + TYPE_COST[att[j-1][1]]
                if c2 < best: best, b = c2, 2
            cost[i, j], back[i, j] = best, b
    i, j, asg = n, m, [-1] * n
    while i > 0:
        b = back[i, j]
        if b == 2: asg[i-1] = j - 1; i -= 1; j -= 1
        elif b == 1: i -= 1
        else: j -= 1
    return cost[n, m], asg

def anchor_shift(db, hop, att, word_t, thr_p, min_pause=0.2):
    """Median offset between clear pause-end attacks and the nearest word start."""
    wt = np.array(word_t); offs = []
    for at, k in att:
        if k != "P": continue
        i = j = int(at / hop)
        while j > 0 and db[j-1] < thr_p: j -= 1
        if (i - j) * hop >= min_pause:
            offs.append(at - wt[np.argmin(abs(wt - at))])
    return float(np.median(offs)) if len(offs) >= 5 else None

def align(word_t, att, shift=None):
    if shift is None:   # brute force when there are not enough clear anchors
        shifts = np.arange(-0.40, 0.401, 0.01)
        shift = min((match(word_t, att, s)[0], s) for s in shifts)[1]
    _, asg = match(word_t, att, shift)
    out = [att[a][0] if a >= 0 else t + shift for t, a in zip(word_t, asg)]
    for k in range(1, len(out)):          # keep monotonic
        out[k] = max(out[k], out[k-1] + 0.04)
    return out, shift, asg

def synthetic_test(seed=1):
    rng = np.random.default_rng(seed)
    true, kinds, t = [], [], 0.5
    for _ in range(150):
        gap = rng.choice([0.25, 0.35, 0.5, 0.9], p=[.4, .3, .2, .1])
        t += gap; true.append(t); kinds.append("P" if gap >= 0.5 else rng.choice(["A", "B"]))
    att = list(zip(true, kinds))
    att += [(x, "B") for x in rng.uniform(0.5, t, 40)]          # spurious attacks
    att.sort()
    shift = 0.18
    noise = np.where(np.array(kinds) == "P", rng.uniform(-0.36, 0.0, len(true)), rng.uniform(-0.15, 0.15, len(true)))
    words = [x - shift + e for x, e in zip(true, noise)]
    got, s, _ = align(words, att)
    err = np.abs(np.array(got) - np.array(true))
    ep = err[np.array(kinds) == "P"]
    return dict(shift_found=round(s, 3), p95_all_ms=round(float(np.percentile(err, 95))*1000, 1),
                p95_after_pause_ms=round(float(np.percentile(ep, 95))*1000, 1))

if __name__ == "__main__":
    if sys.argv[1] == "test":
        print(json.dumps([synthetic_test(s) for s in range(3)])); sys.exit()
    wav, words_json, out = sys.argv[1:4]
    x, sr = load(wav); db, hop = envelope(x, sr)
    att, thr = detect_attacks(db, hop)
    d = json.load(open(words_json))
    words = []
    for t in d["transcription"]:
        w = t["text"].strip()
        if not w: continue
        if all(not c.isalnum() for c in w) and words:      # dash etc. -> punctuation of previous word
            words[-1]["w"] += " " + w; continue
        words.append(dict(w=w, t0_raw=t["offsets"]["from"]/1000, t1_raw=t["offsets"]["to"]/1000))
    wt = [w["t0_raw"] for w in words]
    starts, shift, asg = align(wt, att, anchor_shift(db, hop, att, wt, thr["thr_p"]))
    for w, s, a in zip(words, starts, asg):
        w["t0"] = round(s, 3); w["attack"] = att[a][1] if a >= 0 else None
    for k, w in enumerate(words):
        nxt = words[k+1]["t0"] if k + 1 < len(words) else w["t1_raw"] + shift
        w["t1"] = round(min(max(w["t1_raw"] + shift, w["t0"] + 0.08), nxt), 3)
    json.dump(dict(shift=round(shift, 3), thresholds=thr, n_attacks=len(att),
                   matched=sum(a >= 0 for a in asg), words=words), open(out, "w"), ensure_ascii=False, indent=1)
    print(f"shift {shift:+.3f}s, attacks {len(att)}, matched {sum(a >= 0 for a in asg)}/{len(words)}")
