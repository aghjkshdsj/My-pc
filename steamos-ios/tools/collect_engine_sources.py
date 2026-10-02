#!/usr/bin/env python3
"""Collect exact engine inputs/recipes/configs without gigabytes of object files."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import tarfile

def collect(root):
    build = root / 'build-iOS-arm64'
    archives = sorted(p for p in build.glob('*.tar.*') if p.is_file())
    assert any(p.name == 'qemu-10.0.12-utm.tar.xz' for p in archives)
    assert len(archives) == 7, 'Unexpected CPU engine source set'
    context = build / 'libucontext.git'
    revision = subprocess.check_output(['git', '-C', str(context), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == '9b1d8f01a6e99166f9808c79966abe10786de8b6'
    context_tar = root / 'libucontext-source.tar'
    subprocess.run(['git', '-C', str(context), 'archive', '--format=tar', '-o', str(context_tar.resolve()), 'HEAD'], check=True)
    receipt = {'schema': 1, 'libucontext_revision': revision, 'source_archives': {
        p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()}
        for p in archives + [context_tar]}, 'scope': 'cpu-engine-corresponding-build-inputs'}
    source_receipt = root / 'source-receipt.json'
    source_receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    configs = [p for p in build.rglob('*') if p.is_file() and p.name in {
        'config.log', 'config.status', 'config-host.mak', 'config-meson.cross',
        'config-host.h', 'meson-auto.cross', 'meson-auto-native.ini'}]
    output = root / 'CPU-Engine-Corresponding-Source.tar.gz'
    with tarfile.open(output, 'w:gz') as target:
        for name in ['scripts', 'patches', 'recipe-receipt.json', 'source-receipt.json', 'libucontext-source.tar']:
            target.add(root / name, arcname=name)
        for path in archives + configs:
            target.add(path, arcname=path.relative_to(root).as_posix())
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=pathlib.Path)
    collect(parser.parse_args().root)
