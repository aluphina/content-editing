"""Light working proxy of the cut (SDR, 432x768, GOP 1 s). Not used for picture or final mask."""
import json, subprocess, sys
TONEMAP = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
def main(src, edl, out, w=432, h=768):
    segs = json.load(open(edl))["segments"]
    sel = "+".join(f"between(n,{s['f_in']},{s['f_out']-1})" for s in segs)
    fc = f"[0:v]select='{sel}',setpts=N/25/TB,scale={w}:{h},{TONEMAP}[out]"
    subprocess.run(["ffmpeg","-v","error","-y","-i",src,"-filter_complex",fc,"-map","[out]","-c:v","libx264","-crf","20","-g","25","-preset","fast",
                    "-color_range","tv","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709",out], check=True)
if __name__ == "__main__": main(*sys.argv[1:4])
