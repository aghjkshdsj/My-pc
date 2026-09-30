#!/usr/bin/env python3
"""Embed tested iOS frameworks and a checksummed, compressed Linux guest."""
import gzip
import hashlib
import json
import pathlib
import plistlib
import shutil
import subprocess
import sys

guest, runtime, app = map(pathlib.Path, sys.argv[1:])
frameworks = runtime / 'Frameworks'
embedded = app / 'Frameworks'
embedded.mkdir(exist_ok=True)
pending = ['qemu-aarch64-softmmu.framework']
done = set()
while pending:
    name = pending.pop()
    if name in done:
        continue
    source = frameworks / name
    info = plistlib.loads((source / 'Info.plist').read_bytes())
    binary = source / info['CFBundleExecutable']
    subprocess.run(['xcrun', 'lipo', str(binary), '-verify_arch', 'arm64'], check=True)
    platform = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
    if not any(line.strip() == 'platform IOS' for line in platform.splitlines()):
        raise SystemExit(f'Not an iPhone framework: {name}')
    dependencies = subprocess.check_output(['otool', '-L', str(binary)], text=True)
    for line in dependencies.splitlines()[1:]:
        dependency = line.strip().split(' (', 1)[0]
        if dependency.startswith(('/usr/lib/', '/System/Library/')):
            continue
        if dependency.startswith('@rpath/') and '.framework/' in dependency:
            framework = dependency.split('/')[1]
            if '/' in framework or not (frameworks / framework).is_dir():
                raise SystemExit(f'Missing dependency: {dependency}')
            pending.append(framework)
        else:
            raise SystemExit(f'Host library leaked into iPhone framework: {dependency}')
    shutil.copytree(source, embedded / name, symlinks=True, dirs_exist_ok=True)
    # The IPA is unsigned; the user's sideloading tool signs its frameworks.
    subprocess.run(['codesign', '--remove-signature', str(embedded / name / info['CFBundleExecutable'])], check=True)
    done.add(name)
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
    'Builds with graphics.json default to Metal unless Software was explicitly chosen. Other builds use software.\n'
    'The monitor distinguishes selection from the actual guest renderer/pixel-readback check. GPU utilization and Steam CEF acceleration on a physical phone are not implied.\n')
print('Embedded iOS framework closure:', ', '.join(sorted(done)))
print(json.dumps(manifest, indent=2))
