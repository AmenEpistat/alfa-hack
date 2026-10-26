#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv pip compile server/pyproject.toml parser/pyproject.toml ranking_module/pyproject.toml \
  --python-version 3.12 --python-platform x86_64-unknown-linux-gnu \
  --torch-backend cpu --generate-hashes --emit-index-url \
  --default-index https://pypi.org/simple --output-file docker/requirements.lock
# uv's automatic torch backend selection is not exported as an index directive.
# pip in the Docker image needs that explicit source for the locked +cpu build.
python3 - <<'PY'
from pathlib import Path
p = Path('docker/requirements.lock')
s = p.read_text()
if '--extra-index-url https://download.pytorch.org/whl/cpu' not in s:
    s = s.replace('--index-url https://pypi.org/simple\n', '--index-url https://pypi.org/simple\n--extra-index-url https://download.pytorch.org/whl/cpu\n', 1)
p.write_text(s)
PY
