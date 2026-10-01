#!/usr/bin/env python3
"""Embed tested iOS frameworks and a checksummed, compressed Linux guest."""
import gzip
import hashlib
import json
import pathlib
import shutil
import sys
import importlib.util

guest, runtime, app = map(pathlib.Path, sys.argv[1:])
frameworks = runtime / 'Frameworks'
embedded = app / 'Frameworks'
embedded.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('framework_closure', pathlib.Path(__file__).with_name('framework-closure.py'))
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)
metal = (guest / 'graphics.json').is_file()
done = closure.copy_frameworks(frameworks, embedded, metal=metal, platform='IOS')
shutil.copytree(runtime / 'qemu', app / 'QEMU', dirs_exist_ok=True)
bundled = app / 'LinuxRuntime'
bundled.mkdir(exist_ok=True)
manifest = {'schema': 1, 'architecture': 'aarch64', 'files': []}
for name in ['Image', 'initrd.img', 'rootfs.raw']:
    source = guest / name
    compressed = name == 'rootfs.raw'
    digest = hashlib.sha256()
    destination = bundled / (name + '.gz' if compressed else name)
    with source.open('rb') as reader, (gzip.open(destination, 'wb', compresslevel=3) if compressed else destination.open('wb')) as writer:
        while block := reader.read(1024 * 1024):
            digest.update(block)
            writer.write(block)
    manifest['files'].append({'name': name, 'bytes': source.stat().st_size, 'sha256': digest.hexdigest(), 'gzip': compressed})
(bundled / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
for name in ['packages.tsv', 'runtime.json']:
    shutil.copy2(guest / name, bundled / name)
if (guest / 'graphics.json').exists():
    for name in ['graphics.json', 'graphics-initrd.img']:
        shutil.copy2(guest / name, bundled / name)
(bundled / 'README.txt').write_text('ARM64 Linux experimental runtime for My-pc.\n'
    'QEMU v10.0.12-utm / UTM 7eadb056ae0f91d979059544d0ddcd2d5a40be92.\n'
    'Source and build instructions accompany the release. Guest package copyright notices are in /usr/share/doc.\n'
    'Steam is fetched directly from Valve at first launch; no Valve client binaries are bundled.\n'
    'TCG JIT, selectable/all-available vCPUs, 2048 MiB guest RAM. No iPhone performance result is implied.\n'
    'Metal is experimental and must be selected before startup. Software remains the default and recovery option.\n'
    'The monitor distinguishes selection from the actual guest renderer/pixel-readback check. GPU utilization and Steam CEF acceleration on a physical phone are not implied.\n')
print('Embedded iOS framework closure:', ', '.join(sorted(done)))
print(json.dumps(manifest, indent=2))
