#!/usr/bin/env python3
"""Stage checked CPU engine/payload into a freshly built app, no old input."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import shutil
import tarfile
from verify_ipa import macho_platform

def digest(path):
    with path.open('rb') as file: return hashlib.file_digest(file, 'sha256').hexdigest()

def verify_assets(folder, expected):
    rows = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split(None, 1)
        rows[name.strip()] = checksum
    for name in expected:
        assert name in rows and digest(folder / name) == rows[name], name

def extract_checked(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(source) as archive:
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert not member.issym() and not member.islnk() and not member.isdev(), member.name
        archive.extractall(destination, filter='data')

def bundle(engine, guest, app):
    assert app.is_dir() and (app / 'Info.plist').exists()
    verify_assets(engine, ['CPU-Engine-iOS-Frameworks.tar.gz', 'CPU-Engine-Corresponding-Source.tar.gz'])
    verify_assets(guest, ['Linux-Gate-Payload.tar.gz', 'Linux-Gate-Corresponding-Source.tar.gz'])
    framework_stage = app.parent.parent / 'engine-stage'
    payload_stage = app / 'LinuxGate'
    extract_checked(engine / 'CPU-Engine-iOS-Frameworks.tar.gz', framework_stage)
    extract_checked(guest / 'Linux-Gate-Payload.tar.gz', payload_stage)
    frameworks = framework_stage / 'Frameworks'
    assert (frameworks / 'qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu').exists()
    needed, pending = set(), ['qemu-aarch64-softmmu']
    while pending:
        name = pending.pop()
        if name in needed: continue
        directory = frameworks / (name + '.framework')
        info = plistlib.loads((directory / 'Info.plist').read_bytes())
        binary = directory / info['CFBundleExecutable']
        for dependency in macho_platform(binary.read_bytes(), 6):
            if dependency.startswith('/usr/lib/') or dependency.startswith('/System/Library/'): continue
            assert dependency.startswith('@rpath/') and 'Hypervisor' not in dependency
            parts = pathlib.PurePosixPath(dependency[len('@rpath/'):]).parts
            assert len(parts) == 2 and parts[0].endswith('.framework') and '..' not in parts
            pending.append(parts[0][:-len('.framework')])
        needed.add(name)
    for name in sorted(needed):
        shutil.copytree(frameworks / (name + '.framework'), app / 'Frameworks' / (name + '.framework'))
    for metadata in (app / 'Frameworks').glob('*.framework/Info.plist'):
        value = plistlib.loads(metadata.read_bytes())
        value['CFBundlePackageType'] = 'FMWK'
        value['CFBundleSupportedPlatforms'] = ['iPhoneOS']
        value['DTPlatformName'] = 'iphoneos'
        metadata.write_bytes(plistlib.dumps(value))
    kernel = json.loads((payload_stage / 'kernel-test.json').read_text())
    assert kernel['scope'] == 'hosted-linux-tcg-kernel-test' and kernel['physical_iphone'] is False
    assert kernel['guest']['failures'] == 0
    # This past hosted result is provenance only. The phone generates a new
    # nonce and guest result; it never accepts this file as device evidence.
    inputs = {'schema': 1, 'scope': 'bundled-disposable-linux-cpu-gate',
        'phone_boot_verified': False, 'steamos': False, 'graphics_tested': False,
        'retained_engine_frameworks': sorted(needed),
        'source_assets': {name: digest(folder / name) for folder, name in [
            (engine, 'CPU-Engine-Corresponding-Source.tar.gz'),
            (guest, 'Linux-Gate-Corresponding-Source.tar.gz')]}}
    (payload_stage / 'bundle-inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    info['CFBundleVersion'] = '4000003'
    (app / 'Info.plist').write_bytes(plistlib.dumps(info))
    print(json.dumps(inputs, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['engine', 'guest', 'app']: parser.add_argument(name, type=pathlib.Path)
    args = parser.parse_args()
    bundle(args.engine, args.guest, args.app)
