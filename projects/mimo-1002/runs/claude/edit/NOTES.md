# Пересборка (runs/claude)

Все числа — в edit/data.json (генерирует scripts/build_data.py из words.json/edl.json/track.json).

| что поменять | команды | время |
|---|---|---|
| текст/тайминги графики, субтитры | `python3 scripts/build_data.py && python3 scripts/camera.py edit/data.json edit/camera_states.json && python3 scripts/gen_comp.py edit/data.json edit/comp` → рендер front → composite | ~8 мин |
| камера (зумы, split, кружок) | camera.py → plate.py (перерисует только изменившиеся куски, кеш по ключу) → gen_comp → front → composite | 2–14 мин |
| цвет | правка `grade` в data.json → `make_lut.py` → plate.py (все куски) → composite | ~20 мин |
| звук | `python3 scripts/sfx.py edit/data.json edit/audio/voice_cut.wav edit/audio/mix.wav edit/sfx_catalog.json` → composite | ~6 мин |
| дерёш | derush.py → assemble_audio.py → всё дальше | ~40 мин |

Рендер слоёв: `cd edit/comp/front && HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1 hyperframes render --format mov --fps 25 -w 2 -o ../front.mov` (то же для behind).
**--fps 25 обязателен** (по умолчанию HyperFrames рендерит 30 к/с).
Сведение: `python3 scripts/composite.py edit/data.json edit/plate/concat.txt edit/comp/behind.mov edit/matte/ucl_matte.mov 1257 1313 edit/comp/front.mov edit/audio/mix.wav out/final.mp4 tv` (2 прохода, ~5 мин).
Полный скрипт: edit/rebuild.sh. Проверки: scripts/plan_checks.py, scripts/final_checks.py.
