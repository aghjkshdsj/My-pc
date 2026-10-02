#!/usr/bin/env python3
"""Separate EGL-enabled virgl/Venus engine build for the QEMU graphics path."""
import argparse
import json
import os
import pathlib
import shutil
import tarfile

from build_venus_ios import PROJECT, PINS, capture, clone, digest, framework, headers, run
from verify_ipa import macho_platform

ANGLE_RUN = 37075043878
ANGLE_SOURCE = '8fc4d429b8fd3158ddb9f9c0f2f51414e2e84f8f'


def angle_inputs(artifact, output):
    receipt = json.loads((artifact / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['scope'] == 'source-built-native-ios-angle-engine-compile-only'
    assert receipt['source_commit'] == ANGLE_SOURCE and int(receipt['workflow_run']) == ANGLE_RUN
    assert receipt['engine_commit'] == 'ed78ab6e1a37f4f11583a0bd038f22ec91f3ff10'
    assert receipt['physical_ios_arm64'] is True and receipt['metal_owner_identity_enabled'] is False
    # Copy only regular framework/header files, never trust archive paths/links.
    with tarfile.open(artifact / 'ANGLE-iOS-Frameworks.tar.gz') as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            assert member.isfile() and member.size < 256 * 1024 * 1024
            name = pathlib.PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts
            assert name.parts[0] in ['Frameworks', 'include']
            target = output.joinpath(*name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    for name in ['EGL', 'GLESv2']:
        binary = output / 'Frameworks' / (name + '.framework') / name
        expected = receipt['files'][binary.relative_to(output).as_posix()]
        assert binary.stat().st_size == expected['bytes'] and digest(binary) == expected['sha256']
        macho_platform(binary.read_bytes(), 6)
    assert (output / 'include/EGL/egl.h').is_file()
    return receipt


def build(moltenvk, angle):
    assert os.uname().sysname == 'Darwin'
    output = PROJECT / 'out/ios-gl-venus'
    assert not output.exists(), 'Fresh output required; retain the Venus-only baseline'
    output.mkdir(parents=True)
    angle_receipt = angle_inputs(angle, output)
    vk_headers = output / 'vk-headers'
    headers(moltenvk / 'MoltenVK-Corresponding-Source.tar.gz', vk_headers)
    epoxy = clone('libepoxy', output)
    renderer = clone('virglrenderer', output)
    dispatch = epoxy / 'src/dispatch_common.c'
    text = dispatch.read_text(encoding='utf-8')
    old = '#define EGL_LIB "EGL.framework/EGL"'
    assert text.count(old) == 1
    text = text.replace(old, '#define EGL_LIB "@rpath/EGL.framework/EGL"')
    old = '#define GLES2_LIB "GLESv2.framework/GLESv2"'
    assert text.count(old) == 1
    dispatch.write_text(text.replace(old, '#define GLES2_LIB "@rpath/GLESv2.framework/GLESv2"'), encoding='utf-8')
    epoxy_patch = output / 'ios-egl-dispatch.patch'
    epoxy_patch.write_text(capture('git', '-C', str(epoxy), 'diff') + '\n', encoding='utf-8')
    loader = renderer / 'src/venus/vkr_library.c'
    text = loader.read_text(encoding='utf-8')
    old = '   lib->handle = dlopen("libvulkan.dylib", RTLD_NOW | RTLD_LOCAL);'
    assert text.count(old) == 1
    loader.write_text(text.replace(old, '   lib->handle = dlopen("@rpath/MoltenVK.framework/MoltenVK", RTLD_NOW | RTLD_LOCAL);\n'
                                  '   if (lib->handle == NULL)\n' + old), encoding='utf-8')
    renderer_patch = output / 'ios-vulkan-loader.patch'
    renderer_patch.write_text(capture('git', '-C', str(renderer), 'diff') + '\n', encoding='utf-8')
    prefix = output / 'sysroot'
    flags = ['-target', 'arm64-apple-ios26.0', '-isysroot', capture('xcrun', '--sdk', 'iphoneos', '--show-sdk-path'),
             '-I' + str(vk_headers), '-I' + str(output / 'include')]
    cross = output / 'ios-arm64.cross'
    cross.write_text('\n'.join([
        '[binaries]', "c = ['xcrun', '--sdk', 'iphoneos', 'clang']", "objc = ['xcrun', '--sdk', 'iphoneos', 'clang']",
        "ar = ['xcrun', 'ar']", "strip = ['xcrun', 'strip']", "pkg-config = 'pkg-config'",
        '[host_machine]', "system = 'darwin'", "cpu_family = 'aarch64'", "cpu = 'arm64'", "endian = 'little'",
        '[properties]', 'needs_exe_wrapper = true', 'pkg_config_libdir = ' + repr([str(prefix / 'lib/pkgconfig')]),
        '[built-in options]', 'c_args = ' + repr(flags), 'c_link_args = ' + repr(flags),
        'objc_args = ' + repr(flags), 'objc_link_args = ' + repr(flags), '']), encoding='utf-8')
    common = ['--cross-file', str(cross), '--prefix', str(prefix), '--libdir', 'lib',
              '--buildtype=release', '--default-library=shared', '--wrap-mode=nofallback']
    run('meson', 'setup', str(epoxy / 'build'), str(epoxy), *common,
        '-Dtests=false', '-Ddocs=false', '-Dglx=no', '-Degl=yes', '-Dx11=false')
    run('meson', 'compile', '-C', str(epoxy / 'build'), '-j', '3')
    run('meson', 'install', '-C', str(epoxy / 'build'))
    run('meson', 'setup', str(renderer / 'build'), str(renderer), *common,
        '-Dvenus=true', '-Dneptune=false', '-Dvulkan-dload=true', '-Dvulkan-preload=false',
        '-Dplatforms=egl', '-Dvideo=false', '-Dtests=false', '-Dvtest=false', '-Ddrm-renderers=[]',
        '-Drender-server-mode=thread', '-Drender-server-worker=thread')
    run('meson', 'compile', '-C', str(renderer / 'build'), '-j', '3')
    run('meson', 'install', '-C', str(renderer / 'build'))
    binaries = [framework(prefix / 'lib/libepoxy.0.dylib', 'epoxy.0', output),
                framework(prefix / 'lib/libvirglrenderer.1.dylib', 'virglrenderer.1', output)]
    config = (renderer / 'build/config.h').read_text(encoding='utf-8')
    for define in ['ENABLE_VENUS', 'ENABLE_SAME_PROCESS_RENDER_SERVER', 'HAVE_EPOXY_EGL_H']:
        assert '#define ' + define + ' 1' in config, define
    assert '#define ENABLE_NEPTUNE 1' not in config
    assert 'epoxy_has_egl=1' in (prefix / 'lib/pkgconfig/epoxy.pc').read_text(encoding='utf-8')
    for binary in binaries:
        dependencies = macho_platform(binary.read_bytes(), 6)
        assert not any('IOKit' in name or 'Hypervisor' in name or '/PrivateFrameworks/' in name for name in dependencies)
        for dependency in dependencies:
            if dependency.startswith(('/System/Library/', '/usr/lib/')):
                continue
            assert dependency.startswith('@rpath/') and (output / 'Frameworks' / dependency.removeprefix('@rpath/')).is_file()
    exports = capture('xcrun', 'nm', '-gU', str(binaries[1]))
    for name in ['virgl_renderer_init', 'virgl_renderer_submit_cmd', 'virgl_renderer_get_cap_set',
                 'virgl_renderer_resource_create_blob', 'virgl_renderer_resource_map', 'virgl_renderer_resource_unmap']:
        assert '_' + name in exports, name
    inputs = [cross, epoxy_patch, renderer_patch, output / 'virglrenderer-source.tar', output / 'libepoxy-source.tar']
    receipt = {'schema': 1, 'scope': 'source-built-native-ios-gl-venus-engine-compile-only',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'pins': {name: revision for name, (_, revision) in PINS.items()}, 'angle_input': angle_receipt,
               'physical_ios_arm64': True, 'egl_backend_compiled': True, 'venus_backend_compiled': True,
               'same_process_thread_renderer': True, 'phone_tested': False, 'linux_graphics_verified': False,
               'memory_import_verified': False, 'metal_runtime_verified': False, 'presentation_verified': False,
               'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in inputs + binaries}}
    receipt_path = output / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    # Preserve the build prefix and exact headers/pkg-config for a later QEMU build.
    shutil.copytree(output / 'include', prefix / 'include', dirs_exist_ok=True)
    with tarfile.open(output / 'GL-Venus-iOS-Frameworks.tar.gz', 'w:gz') as archive:
        archive.add(output / 'Frameworks', arcname='Frameworks')
        archive.add(prefix, arcname='sysroot')
        archive.add(vk_headers, arcname='vk-headers')
    with tarfile.open(output / 'GL-Venus-Corresponding-Source.tar.gz', 'w:gz') as archive:
        for path in inputs + [receipt_path, renderer / 'build/config.h', PROJECT / 'tools/build_gl_venus_ios.py',
                              PROJECT / 'tools/build_venus_ios.py', PROJECT / 'tools/verify_ipa.py',
                              PROJECT / 'tools/bundle_native_vulkan.py', PROJECT.parent / '.github/workflows/steamos-ios-gl-venus.yml']:
            archive.add(path, arcname=path.name)
        archive.add(angle / 'ANGLE-Corresponding-Source.tar.gz', arcname='ANGLE-Corresponding-Source.tar.gz')
        archive.add(moltenvk / 'MoltenVK-Corresponding-Source.tar.gz', arcname='MoltenVK-and-Headers-Corresponding-Source.tar.gz')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('moltenvk_artifact', type=pathlib.Path)
    parser.add_argument('angle_artifact', type=pathlib.Path)
    args = parser.parse_args()
    build(args.moltenvk_artifact.resolve(), args.angle_artifact.resolve())
