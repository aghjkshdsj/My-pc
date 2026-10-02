#!/usr/bin/env python3
"""Exact public source allowlist. Never exports old projects or device logs."""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
paths = [root / '.gitignore', root / 'README.md']
for folder in ['Host', 'Guest', 'tools', 'tests', 'docs', 'MyPCSteamOS.xcodeproj']:
    paths += sorted(p for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths += [root / 'evidence' / name for name in ['archive-summary.json', 'archive-files.csv']]
paths += [root / 'evidence/primary' / name for name in ['receipts.json', 'steam-arm-stable.vdf', 'steam-arm-beta.vdf']]
paths += [root.parent / '.github/workflows/steamos-ios-probe.yml']
paths = sorted(set(paths))
rows = [{'path': p.relative_to(root.parent).as_posix(), 'mode': '100644', 'type': 'blob',
         'content': p.read_text(encoding='utf-8')} for p in paths]
if len(sys.argv) > 1 and sys.argv[1] == '--without-inventory':
    rows = [x for x in rows if not x['path'].endswith('archive-files.csv')]
print(json.dumps(rows, ensure_ascii=True))
