#!/usr/bin/env python3
"""Resolve the reference's old research/dxmt-relative configuration include."""
from pathlib import Path

source_path = Path('dxmt/src/winemetal/unix/winemetal_unix.c')
source = source_path.read_text()
old = '#include "../../../../../build/madeira_cfg.h"'
if source.count(old) != 1:
    raise SystemExit('DXMT configuration include marker changed')
source = source.replace(old, '#include "madeira_cfg.h"', 1)
old = '#include "../../../../remote-metal/host/wmt_decode.h"'
if source.count(old) != 1:
    raise SystemExit('DXMT optional remote decoder include marker changed')
source = source.replace(old, '#include "../../../../research/remote-metal/host/wmt_decode.h"', 1)
source_path.write_text(source)

build_path = Path('build/dxmt-ios/build.sh')
script = build_path.read_text()
old = 'COMMON_FLAGS="-arch arm64'
if script.count(old) != 1:
    raise SystemExit('DXMT native include flags marker changed')
build_path.write_text(script.replace(old, 'COMMON_FLAGS="-I$REPO_ROOT/build -arch arm64', 1))
