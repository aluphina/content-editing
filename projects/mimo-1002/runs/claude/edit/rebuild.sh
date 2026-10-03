set -e
cd /home/user/content-editing/projects/mimo-1002/runs/claude
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1
python3 scripts/plate.py edit/data.json edit/edl.json ../../takes/take1.mp4 edit/grade/autumn.cube edit/plate
echo PLATE_DONE
(cd edit/comp/front && hyperframes render --format mov --fps 25 -w 2 -o ../front.mov 2>&1 | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tr '\r' '\n' | grep -E "MB ·")
echo FRONT_DONE
python3 scripts/composite.py edit/data.json edit/plate/concat.txt edit/comp/behind.mov edit/matte/ucl_matte.mov 1257 1313 edit/comp/front.mov edit/audio/mix.wav out/final.mp4 tv
echo ALL_DONE
