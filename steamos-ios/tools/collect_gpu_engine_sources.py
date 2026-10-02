#!/usr/bin/env python3
"""Audit the new GPU engine and retain complete source/recipes/configs/licenses."""
import argparse
import hashlib
import json
import os
import pathlib
import plistlib
import re
import subprocess
import tarfile

from verify_ipa import macho_platform

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collect(root, graphics_artifact):
    build = root / 'build-iOS-arm64'
    prefix = root / 'sysroot-iOS-arm64'
    frameworks = prefix / 'Frameworks'
    engine = frameworks / 'qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu'
    macho_platform(engine.read_bytes(), 6)
    symbols = subprocess.check_output(['xcrun', 'nm', '-gU', str(engine)], text=True)
    for name in ['qemu_init', 'qemu_main_loop', 'qemu_cleanup']:
        assert '_' + name in symbols, name
    config_paths = [p for p in build.rglob('config-host.h') if any(part.startswith('qemu-') for part in p.parts)]
    assert len(config_paths) == 1, config_paths
    config = config_paths[0].read_text(encoding='utf-8')
    for define in ['CONFIG_OPENGL', 'CONFIG_EGL', 'CONFIG_METAL', 'VIRGL_VERSION_MAJOR']:
        assert re.search(r'^#define[ \t]+' + define + r'(?:[ \t]+1)?[ \t]*$', config, re.MULTILINE), define
    for define in ['CONFIG_HVF', 'CONFIG_HVF_PRIVATE']:
        assert not re.search(r'^#define[ \t]+' + define + r'(?:[ \t]+1)?[ \t]*$', config, re.MULTILINE)
    data = engine.read_bytes()
    assert b'virtio-gpu-gl' in data and b'egl-headless' in data
    assert b'MPC ANGLE Metal root context creation failed' in data
    imports = {}
    for info_path in frameworks.glob('*.framework/Info.plist'):
        info = plistlib.loads(info_path.read_bytes())
        binary = info_path.parent / info['CFBundleExecutable']
        dependencies = macho_platform(binary.read_bytes(), 6)
        imports[binary.relative_to(root).as_posix()] = dependencies
        assert not any('IOKit' in name or 'Hypervisor' in name or '/PrivateFrameworks/' in name for name in dependencies)
        for dependency in dependencies:
            if dependency.startswith(('/System/Library/', '/usr/lib/')):
                continue
            assert dependency.startswith('@rpath/'), dependency
            assert (frameworks / dependency.removeprefix('@rpath/')).is_file(), dependency
    for name in ['EGL', 'GLESv2', 'epoxy.0', 'virglrenderer.1']:
        assert (frameworks / (name + '.framework') / name).is_file()
    archives = sorted(build.glob('*.tar.*'))
    assert len(archives) == 7 and any(p.name == 'qemu-10.0.12-utm.tar.xz' for p in archives)
    context = build / 'libucontext.git'
    revision = subprocess.check_output(['git', '-C', str(context), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == '9b1d8f01a6e99166f9808c79966abe10786de8b6'
    context_tar = root / 'libucontext-source.tar'
    subprocess.run(['git', '-C', str(context), 'archive', '--format=tar', '-o', str(context_tar), 'HEAD'], check=True)
    binary_paths = [p for p in frameworks.rglob('*') if p.is_file() and p.suffix != '.plist']
    receipt = {'schema': 1, 'scope': 'source-built-physical-ios-qemu-gpu-engine-compile-only',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'recipe': json.loads((root / 'recipe-receipt.json').read_text(encoding='utf-8')),
               'graphics_dependency': json.loads((root / 'gpu-dependency-receipt.json').read_text(encoding='utf-8')),
               'adapter': json.loads((root / 'gpu-adapter-source.json').read_text(encoding='utf-8')),
               'libucontext_commit': revision, 'physical_ios_arm64': True,
               'opengl_virgl_compiled': True, 'venus_device_compiled': True,
               'metal_egl_backend_explicit': True, 'hardware_virtualization': False,
               'phone_tested': False, 'linux_graphics_verified': False,
               'memory_import_verified': False, 'metal_runtime_verified': False,
               'presentation_verified': False, 'gameplay_verified': False,
               'imports': imports,
               'files': {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)}
                         for p in archives + [context_tar] + binary_paths}}
    receipt_path = root / 'gpu-engine-receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    configs = [p for p in build.rglob('*') if p.is_file() and p.name in {
        'config.log', 'config.status', 'config-host.mak', 'config-meson.cross', 'config-host.h',
        'meson-auto.cross', 'meson-auto-native.ini', 'config-devices.mak'}]
    with tarfile.open(root / 'GPU-Engine-Corresponding-Source.tar.gz', 'w:gz') as archive:
        for name in ['scripts', 'patches', 'recipe-receipt.json', 'gpu-engine-receipt.json',
                     'gpu-dependency-receipt.json', 'gpu-adapter-source.json',
                     'qemu-angle-metal-diagnostic.patch', 'libucontext-source.tar']:
            archive.add(root / name, arcname=name)
        for path in archives + configs:
            archive.add(path, arcname=path.relative_to(root).as_posix())
        archive.add(graphics_artifact / 'GL-Venus-Corresponding-Source.tar.gz', arcname='GL-Venus-Corresponding-Source.tar.gz')
        for name in ['prepare_gpu_engine_build.py', 'prepare_engine_build.py', 'stage_gpu_engine.py',
                     'patch_qemu_gpu.py', 'collect_gpu_engine_sources.py', 'verify_ipa.py']:
            archive.add(PROJECT / 'tools' / name, arcname='fresh-recipes/' + name)
        archive.add(PROJECT.parent / '.github/workflows/steamos-ios-gpu-engine.yml', arcname='steamos-ios-gpu-engine.yml')
    with tarfile.open(root / 'GPU-Engine-iOS-Frameworks.tar.gz', 'w:gz') as archive:
        archive.add(frameworks, arcname='Frameworks')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=pathlib.Path)
    parser.add_argument('graphics_artifact', type=pathlib.Path)
    args = parser.parse_args()
    collect(args.root.resolve(), args.graphics_artifact.resolve())
