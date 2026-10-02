#!/usr/bin/env python3
"""Exact public source allowlist. Never exports old projects or device logs."""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
paths = [root / '.gitignore', root / 'README.md', root / 'LICENSE', root / 'STATUS.md']
for folder in ['Host', 'Guest', 'tools', 'tests', 'docs', 'MyPCSteamOS.xcodeproj']:
    paths += sorted(p for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths += [root / 'evidence' / name for name in ['archive-summary.json', 'archive-files.csv']]
paths += [root / 'evidence/primary' / name for name in ['receipts.json', 'steam-arm-stable.vdf', 'steam-arm-beta.vdf', 'steam-package-plan.json', 'valve-rootfs-metadata.json', 'hosted-vulkan-diagnostic.json', 'hosted-moltenvk-build.json']]
paths += [root.parent / '.github/workflows' / name for name in ['steamos-ios-probe.yml', 'steamos-linux-kernel-gate.yml', 'steamos-ios-engine.yml', 'steamos-linux-source-gate.yml', 'steamos-graphics-diagnostic.yml', 'steamos-ios-linux-prerelease.yml', 'steamos-rootfs-inspect.yml', 'steamos-evidence.yml', 'steamos-ios-moltenvk.yml', 'steamos-venus-transport.yml']]
paths += [root.parent / '.github/workflows/steamos-moltenvk-artifact-audit.yml']
paths += [root / 'evidence/primary/hosted-venus-shm-diagnostic.json']
paths += [root / 'evidence/primary/ios-native-vulkan-prerelease.json']
paths = sorted(set(paths))
rows = [{'path': p.relative_to(root.parent).as_posix(), 'mode': '100644', 'type': 'blob',
         'content': p.read_text(encoding='utf-8')} for p in paths]
if len(sys.argv) > 1 and sys.argv[1] == '--without-inventory':
    rows = [x for x in rows if not x['path'].endswith('archive-files.csv')]
print(json.dumps(rows, ensure_ascii=True))
