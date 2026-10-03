"""Final assembly in ffmpeg: plate -> behind layer -> person (plate pixels + matte alpha) -> front layer.

HyperFrames writes ProRes 4444 in BT.601 without a matrix tag: read it as bt601. Blend in RGB (gbrp),
then convert once to BT.709 tv with accurate swscale flags and pin the tags with setparams.
"""
import json, sys, subprocess, os

ACC = "accurate_rnd+full_chroma_int+full_chroma_inp"

def graph(d, matte_range, hf_range):
    fps = d["project"]["fps"]
    a, b = matte_range
    to_rgb = f"scale=in_color_matrix=bt601:in_range={hf_range}:out_range=pc:flags={ACC},format=gbrap"
    return ";".join([
        "[0:v]format=gbrp,split=2[base][p2]",
        f"[1:v]{to_rgb}[beh]",
        f"[3:v]{to_rgb}[fr]",
        f"[p2]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[pp]",
        "[2:v]format=yuva444p,alphaextract,format=gray[ma]",
        f"[pp][ma]alphamerge,setpts=PTS+{a}/{fps}/TB[person]",
        "[base][beh]overlay=format=gbrp:eof_action=pass[b1]",
        "[b1][person]overlay=format=gbrp:eof_action=pass[b2]",
        "[b2][fr]overlay=format=gbrp:eof_action=pass[b3]",
        f"[b3]scale=out_color_matrix=bt709:out_range=tv:flags={ACC},format=yuv420p,"
        "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[v]",
    ])

def main(data_json, plate_concat, behind_mov, matte_mov, matte_a, matte_b, front_mov, mix_wav, out, hf_range="tv"):
    d = json.load(open(data_json))
    g = graph(d, (int(matte_a), int(matte_b)), hf_range)
    common = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", plate_concat, "-i", behind_mov, "-i", matte_mov,
              "-i", front_mov, "-i", mix_wav, "-filter_complex", g, "-map", "[v]", "-map", "4:a",
              "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-tune", "grain", "-b:v", "30M", "-maxrate", "45M", "-bufsize", "60M",
              "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
              "-r", str(d["project"]["fps"]), "-frames:v", str(round(d["duration"] * d["project"]["fps"]))]
    logp = os.path.join(os.path.dirname(out), "x264pass")
    subprocess.run(common + ["-pass", "1", "-passlogfile", logp, "-an", "-f", "mp4", "/dev/null"], check=True)
    subprocess.run(common + ["-pass", "2", "-passlogfile", logp, "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out], check=True)
    for f in os.listdir(os.path.dirname(out)):
        if f.startswith("x264pass"): os.remove(os.path.join(os.path.dirname(out), f))
    print("written", out)

if __name__ == "__main__":
    main(*sys.argv[1:])
