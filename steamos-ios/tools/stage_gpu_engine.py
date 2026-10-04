#!/usr/bin/env python3
"""Stage verified physical-iOS graphics libraries into a new QEMU build prefix."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import tarfile

from verify_ipa import macho_platform


def stage(artifact, prefix):
    receipt = json.loads((artifact / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['scope'] == 'source-built-native-ios-gl-venus-engine-compile-only'
    assert int(receipt['workflow_run']) == int(os.environ['MPC_GPU_RENDERER_RUN'])
    assert receipt['source_commit'] == os.environ['MPC_GPU_RENDERER_SOURCE']
    assert all(receipt[name] is True for name in ['physical_ios_arm64', 'egl_backend_compiled',
                                                'venus_backend_compiled', 'same_process_thread_renderer'])
    assert receipt['phone_tested'] is False and receipt['linux_graphics_verified'] is False
    assert receipt['failure_diagnostics']['failure_errno_and_stage_compiled'] is True
    assert receipt['failure_diagnostics']['allocator_policy_changed'] is False
    assert receipt['failure_diagnostics']['success_override'] is False
    private_file = receipt['private_file_backing']
    for field in ['allocator_policy_changed', 'explicit_app_private_directory_required',
                  'atomic_exclusive_create', 'mode_0600', 'unlink_before_mapping',
                  'close_on_exec', 'hosted_native_tests_passed']:
        assert private_file[field] is True
    assert private_file['phone_tested'] is False and private_file['success_override'] is False
    assert private_file['host_memory_import_verified'] is False
    unpacked = prefix.parent / 'gpu-dependency-input'
    assert not unpacked.exists()
    unpacked.mkdir()
    with tarfile.open(artifact / 'GL-Venus-iOS-Frameworks.tar.gz') as archive:
        for member in archive.getmembers():
            name = pathlib.PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts
            # Meson prefixes contain ordinary relative dylib aliases. We copy
            # only checked regular files and recreate the four aliases below.
            if member.isdir() or member.issym():
                continue
            assert member.isfile() and member.size < 256 * 1024 * 1024
            allowed = name.parts[0] in ['Frameworks', 'vk-headers'] or name.parts[:2] == ('sysroot', 'include')
            allowed = allowed or name.parts[:3] == ('sysroot', 'lib', 'pkgconfig')
            if not allowed:
                continue
            destination = unpacked.joinpath(*name.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
    libraries = {'EGL': ('libEGL.dylib', 'libEGL.dylib'),
                 'GLESv2': ('libGLESv2.dylib', 'libGLESv2.dylib'),
                 'epoxy.0': ('libepoxy.0.dylib', 'libepoxy.dylib'),
                 'virglrenderer.1': ('libvirglrenderer.1.dylib', 'libvirglrenderer.dylib')}
    for name, (filename, alias) in libraries.items():
        relative = 'Frameworks/' + name + '.framework/' + name
        binary = unpacked / relative
        source_receipt = receipt['angle_input'] if name in ['EGL', 'GLESv2'] else receipt
        expected = source_receipt['files'][relative]
        assert binary.stat().st_size == expected['bytes']
        with binary.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected['sha256']
        dependencies = macho_platform(binary.read_bytes(), 6)
        assert not any('IOKit' in name or 'Hypervisor' in name or '/PrivateFrameworks/' in name for name in dependencies)
        target = prefix / 'Frameworks' / (name + '.framework')
        assert not target.exists(), 'Do not replace an existing framework'
        shutil.copytree(binary.parent, target)
        destination = prefix / 'lib' / filename
        assert not destination.exists()
        shutil.copy2(binary, destination)
        if alias != filename:
            assert not (prefix / 'lib' / alias).exists()
            (prefix / 'lib' / alias).symlink_to(filename)
    for source in [unpacked / 'sysroot/include', unpacked / 'vk-headers']:
        shutil.copytree(source, prefix / 'include', dirs_exist_ok=True)
    for path in (unpacked / 'sysroot/lib/pkgconfig').glob('*.pc'):
        text = path.read_text(encoding='utf-8')
        values = re.findall(r'^prefix=(.*)$', text, re.MULTILINE)
        assert len(values) == 1
        text = text.replace(values[0], str(prefix))
        destination = prefix / 'lib/pkgconfig' / path.name
        assert not destination.exists()
        destination.write_text(text, encoding='utf-8')
    assert (prefix / 'include/virgl/virglrenderer.h').is_file()
    assert (prefix / 'include/epoxy/egl.h').is_file()
    assert (prefix / 'include/EGL/eglext_angle.h').is_file()
    (prefix.parent / 'gpu-dependency-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=pathlib.Path)
    parser.add_argument('prefix', type=pathlib.Path)
    args = parser.parse_args()
    stage(args.artifact.resolve(), args.prefix.resolve())
