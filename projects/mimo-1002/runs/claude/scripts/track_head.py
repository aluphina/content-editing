"""Per-frame head position from the person-mask proxy (alpha). Coordinates are fractions of frame w/h."""
import subprocess, numpy as np, json, sys
def main(mask_mov, out, w=216, h=384):
    raw = subprocess.run(["ffmpeg","-v","error","-i",mask_mov,"-vf",f"format=yuva444p,alphaextract,scale={w}:{h}:flags=area,format=gray","-f","rawvideo","-pix_fmt","gray","-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    np.save(out.replace(".json", ".npy"), a)
    res = []
    for f in a:
        m = f > 128
        rows = np.where(m.sum(1) > 2)[0]
        if not len(rows): res.append(None); continue
        top = rows[0]
        # head band: from top to where the mask widens past 2.2x the head width (shoulders)
        widths = m.sum(1)
        head_w = np.median(widths[top+int(0.03*h):top+int(0.08*h)])
        band = m[top:top+int(0.13*h)]
        ys, xs = np.nonzero(band)
        cx = xs.mean() / w
        res.append(dict(top=round(top/h, 4), cx=round(float(cx), 4), head_w=round(float(head_w)/w, 4),
                        eye_y=round(top/h + 0.55*float(head_w)/w, 4)))
    json.dump(res, open(out, "w"))
    print(len(res), "frames")
if __name__ == "__main__": main(*sys.argv[1:3])
