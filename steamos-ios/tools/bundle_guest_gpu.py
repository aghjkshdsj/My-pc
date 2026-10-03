#!/usr/bin/env python3
"""Bundle only the audited native engine closure and exact disposable GPU guest."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import tarfile

from verify_ipa import macho_platform, macho_text

ENGINE_RUN = 37078645613
ENGINE_SOURCE = '56f2522eed4509fe2010d2250eaa569dd503c660'
GUEST_RUN = 37079133580
GUEST_SOURCE = 'cb99fc4740385ddcb37119bbc164d5671ea61ce0'


def hashed(data, expected):
    assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']


def closure(receipt):
    roots = ['qemu-aarch64-softmmu', 'EGL', 'GLESv2', 'epoxy.0', 'virglrenderer.1']
    queue = [name + '.framework/' + name for name in roots]
    selected = set()
    prefix = 'sysroot-iOS-arm64/Frameworks/'
    while queue:
        relative = queue.pop()
        if relative in selected:
            continue
        assert prefix + relative in receipt['files'] and prefix + relative in receipt['imports']
        selected.add(relative)
        for dependency in receipt['imports'][prefix + relative]:
            assert not any(word in dependency for word in ['IOKit', 'Hypervisor', '/PrivateFrameworks/'])
            if dependency.startswith(('/System/Library/', '/usr/lib/')):
                continue
            assert dependency.startswith('@rpath/')
            queue.append(dependency.removeprefix('@rpath/'))
    return selected


def bundle(engine_artifact, guest_artifact, app):
    engine = json.loads((engine_artifact / 'gpu-engine-receipt.json').read_text(encoding='utf-8'))
    assert engine['scope'] == 'source-built-physical-ios-qemu-gpu-engine-compile-only'
    assert engine['source_commit'] == ENGINE_SOURCE and int(engine['workflow_run']) == ENGINE_RUN
    assert engine['physical_ios_arm64'] and engine['opengl_virgl_compiled'] and engine['venus_device_compiled']
    assert not engine['hardware_virtualization'] and not engine['phone_tested']
    assert engine['adapter']['root_gles_version_requested'] == 3
    selected = closure(engine)
    framework_names = {p.split('/')[0] for p in selected}
    frames = app / 'Frameworks'
    frames.mkdir(exist_ok=True)
    with tarfile.open(engine_artifact / 'GPU-Engine-iOS-Frameworks.tar.gz') as archive:
        seen = set()
        for member in archive.getmembers():
            if member.isdir():
                continue
            name = pathlib.PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts and name.parts[0] == 'Frameworks'
            assert member.isfile() and member.size < 256 * 1024 * 1024
            assert member.name not in seen
            seen.add(member.name)
            if name.parts[1] not in framework_names:
                continue
            destination = app.joinpath(*name.parts)
            assert not destination.exists(), 'Preserve previously staged frameworks'
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            if name.parts[-1] != 'Info.plist':
                hashed(data, engine['files']['sysroot-iOS-arm64/' + member.name])
                assert set(macho_platform(data, 6)) == set(engine['imports']['sysroot-iOS-arm64/' + member.name])
            destination.write_bytes(data)
    identities = {}
    for relative in sorted(selected):
        path = frames / relative
        info = plistlib.loads((path.parent / 'Info.plist').read_bytes())
        assert info['CFBundleExecutable'] == path.name
        path.chmod(0o755)
        identities[relative] = macho_text(path.read_bytes())
    # MoltenVK is staged separately from the exact already phone-tested build.
    molten = frames / 'MoltenVK.framework/MoltenVK'
    from bundle_native_vulkan import BINARY_SHA
    assert hashlib.sha256(molten.read_bytes()).hexdigest() == BINARY_SHA
    identities['MoltenVK.framework/MoltenVK'] = macho_text(molten.read_bytes())
    payload = app / 'LinuxGuestGPU'
    assert not payload.exists()
    payload.mkdir()
    receipt = json.loads((guest_artifact / 'payload/payload-receipt.json').read_text(encoding='utf-8'))
    assert receipt['scope'] == 'linux-arm64-graphics-payload-missing-3d-boot-controls'
    assert receipt['source_commit'] == GUEST_SOURCE and int(receipt['workflow_run']) == GUEST_RUN
    assert receipt['linux_runtime_boot_verified'] and receipt['runtime_dependency_closure_verified']
    assert not any(receipt[key] for key in ['guest_shader_verified', 'phone_tested', 'metal_verified',
                                           'presentation_verified', 'steamos_verified', 'gameplay_verified'])
    with tarfile.open(guest_artifact / 'Guest-GPU-Payload.tar.gz') as archive:
        for name, expected in receipt['files'].items():
            assert pathlib.PurePosixPath(name).name == name and name in ['Image', 'initramfs.cpio.gz']
            data = archive.extractfile('payload/' + name).read()
            hashed(data, expected)
            (payload / name).write_bytes(data)
    assert (payload / 'Image').read_bytes()[56:60] == b'ARMd'
    (payload / 'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    metadata = {'schema': 1, 'scope': 'bundled-physical-ios-linux-guest-gpu-gate',
                'engine_run': ENGINE_RUN, 'engine_source': ENGINE_SOURCE,
                'guest_run': GUEST_RUN, 'guest_source': GUEST_SOURCE,
                'hardware_virtualization': False, 'root_gles_version_requested': 3,
                'engine_text_sections': identities, 'engine_receipt': engine,
                'guest_shader_verified': False, 'metal_host_verified': False,
                'host_memory_import_verified': False, 'presentation_verified': False,
                'steamos_verified': False, 'gameplay_verified': False}
    (payload / 'engine-bundle.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    info['CFBundleVersion'] = '4000011'
    (app / 'Info.plist').write_bytes(plistlib.dumps(info))
    print(json.dumps({'scope': metadata['scope'], 'build': info['CFBundleVersion'],
                      'frameworks': sorted(identities), 'guest_payload': receipt['files'],
                      'guest_shader_verified': False, 'phone_tested': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['engine_artifact', 'guest_artifact', 'app']:
        parser.add_argument(name, type=pathlib.Path)
    args = parser.parse_args()
    bundle(args.engine_artifact.resolve(), args.guest_artifact.resolve(), args.app.resolve())
