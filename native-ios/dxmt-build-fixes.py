#!/usr/bin/env python3
"""Resolve the reference's old research/dxmt-relative configuration include."""
from pathlib import Path
import re

source_path = Path('dxmt/src/winemetal/unix/winemetal_unix.c')
source = source_path.read_text()
old = '#include "../../../../../build/madeira_cfg.h"'
if source.count(old) != 1:
    raise SystemExit('DXMT configuration include marker changed')
source = source.replace(old, '#include "madeira_cfg.h"', 1)
rewrites = {source_path: source}
old_prefix = '../../../../remote-metal/'
new_prefix = '../../../../research/remote-metal/'
references = 0
for path in [source_path, *sorted(source_path.parent.rglob('*.h'))]:
    text = rewrites.get(path, path.read_text())
    for include in re.findall(r'#\s*include\s+"([^"]+)"', text):
        if include.startswith(old_prefix):
            target = Path('research/remote-metal') / include[len(old_prefix):]
            if not target.is_file():
                raise SystemExit(f'DXMT moved include is missing: {target}')
            references += 1
    if old_prefix in text:
        rewrites[path] = text.replace(old_prefix, new_prefix)
if references < 3:
    raise SystemExit('Unexpected pinned DXMT moved-include layout')

build_path = Path('build/dxmt-ios/build.sh')
script = build_path.read_text()
old = 'COMMON_FLAGS="-arch arm64'
if script.count(old) != 1:
    raise SystemExit('DXMT native include flags marker changed')
rewrites[build_path] = script.replace(old, 'COMMON_FLAGS="-I$REPO_ROOT/build -arch arm64', 1)
for path, content in rewrites.items():
    path.write_text(content)
print(f'Resolved {references} checked DXMT includes after the source-directory move')
