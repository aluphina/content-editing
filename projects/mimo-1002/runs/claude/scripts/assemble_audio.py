"""Cut voice by EDL with 15 ms equal-power crossfades centred on each splice (length preserved)."""
import sys, json, os, wave, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load
XF = 0.015
def main(wav, edl, out):
    x, sr = load(wav); segs = json.load(open(edl))["segments"]
    h = int(XF*sr/2); total = sum(s["f_out"]-s["f_in"] for s in segs) * sr // 25
    y = np.zeros(total + 2*h, np.float32); pos = h
    t = np.linspace(0, np.pi/2, 2*h)
    for k, s in enumerate(segs):
        a, b = s["f_in"]*sr//25, s["f_out"]*sr//25
        piece = x[max(0, a-h):b+h].copy()
        if a-h < 0: piece = np.concatenate([np.zeros(h-a, np.float32), piece])
        if k > 0: piece[:2*h] *= np.sin(t)
        if k < len(segs)-1: piece[-2*h:] *= np.cos(t)
        y[pos-h:pos-h+len(piece)] += piece[:len(y)-(pos-h)]; pos += b-a
    y = y[h:h+total]
    w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(y, -1, 1)*32767).astype(np.int16).tobytes()); w.close()
    print(out, len(y)/sr)
if __name__ == "__main__": main(*sys.argv[1:4])
