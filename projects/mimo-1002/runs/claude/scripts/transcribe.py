"""Split audio at pauses >=0.7 s, transcribe each chunk separately (ru, large-v3-turbo), word-level JSON."""
import sys, json, subprocess, os, wave
sys.path.insert(0, os.path.dirname(__file__))
from envelope import load, envelope, pauses
MODEL = os.path.expanduser("~/models/ggml-large-v3-turbo.bin")

def run(wav48, wav16, out_json, workdir):
    x, sr = load(wav48); db, hop = envelope(x, sr)
    dur = len(x) / sr
    ps = pauses(db, hop, -20, 0.7)
    cuts = [0.0] + [(a+b)/2 for a, b in ps if 0 < a and b < dur] + [dur]
    os.makedirs(workdir, exist_ok=True)
    words = []
    for i, (s, e) in enumerate(zip(cuts, cuts[1:])):
        if e - s < 0.3: continue
        seg = f"{workdir}/seg{i:03d}.wav"
        subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",wav16,seg], check=True)
        subprocess.run(["whisper-cli","-m",MODEL,"-l","ru","-t","4","-ml","1","-sow","-mc","0","-oj","-of",seg[:-4],"-np",seg],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        js = json.load(open(seg[:-4] + ".json"))
        for t in js["transcription"]:
            w = t["text"].strip()
            if not w: continue
            words.append({"w": w, "t0": round(s + t["offsets"]["from"]/1000, 3), "t1": round(s + t["offsets"]["to"]/1000, 3), "chunk": i})
        print(f"chunk {i} {s:.2f}-{e:.2f}:", " ".join(t["text"].strip() for t in js["transcription"]), flush=True)
    json.dump({"source": wav48, "chunks": list(zip(cuts, cuts[1:])), "words": words}, open(out_json, "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    run(*sys.argv[1:5])
