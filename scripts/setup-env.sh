#!/usr/bin/env bash
# Reinstall the video toolchain in a fresh container: HyperFrames CLI + skills,
# headless Chrome, whisper.cpp. Idempotent — safe to re-run.
set -euo pipefail

HF_VERSION="${HF_VERSION:-0.8.115}"

if [ "$(hyperframes --version 2>/dev/null)" != "$HF_VERSION" ]; then
  npm i -g "hyperframes@$HF_VERSION"
fi
hyperframes browser ensure
[ -d ~/.claude/skills/hyperframes ] || hyperframes skills

if ! command -v whisper-cli >/dev/null; then
  mkdir -p ~/src
  [ -d ~/src/whisper.cpp ] || git clone -q --depth 1 https://github.com/ggml-org/whisper.cpp ~/src/whisper.cpp
  cmake -S ~/src/whisper.cpp -B ~/src/whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF >/dev/null
  cmake --build ~/src/whisper.cpp/build -j"$(nproc)" --config Release >/dev/null
  cmake --install ~/src/whisper.cpp/build --prefix /usr/local >/dev/null
  ldconfig 2>/dev/null || true
fi

hyperframes doctor || true
