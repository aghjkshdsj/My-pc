#!/usr/bin/env python3
"""Source-build the pinned native iOS Venus engine; no application reuse.

Build/ABI evidence only. Guest transport, shared-memory import, presentation
and phone execution cannot be marked passed by compiling these libraries.
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import tarfile

from bundle_native_vulkan import SOURCE_SHA
from verify_ipa import macho_platform

PINS = {
    'virglrenderer': ('https://github.com/utmapp/virglrenderer.git', '5d26f605f50f8e22002ec6db5fb775e1992d4e96'),
    'libepoxy': ('https://github.com/utmapp/libepoxy.git', 'bf98587477fe68d07b93319ece7b40a7d0e2eabe'),
}
PROJECT = pathlib.Path(__file__).resolve().parents[1]


def run(*arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def capture(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


def headers(archive, output):
    assert digest(archive) == SOURCE_SHA, 'Wrong Vulkan header corresponding-source archive'
    with tarfile.open(archive) as source:
        nested = source.extractfile('corresponding-source/Vulkan-Headers.tar').read()
    output.mkdir()
    with tarfile.open(fileobj=io.BytesIO(nested)) as source:
        for member in source.getmembers():
            if not member.name.startswith('include/') or not member.isfile():
                continue
            relative = pathlib.PurePosixPath(member.name).relative_to('include')
            assert not relative.is_absolute() and '..' not in relative.parts
            destination = output.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.extractfile(member).read())
    assert (output / 'vulkan/vulkan.h').is_file()


def clone(name, output):
    repository, revision = PINS[name]
    source = output / name
    source.mkdir()
    run('git', '-C', str(source), 'init', '-q')
    run('git', '-C', str(source), 'remote', 'add', 'origin', repository)
    run('git', '-C', str(source), 'fetch', '--depth=1', 'origin', revision)
    run('git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD')
    assert capture('git', '-C', str(source), 'rev-parse', 'HEAD') == revision
    run('git', '-C', str(source), 'archive', '--format=tar', '-o', str(output / (name + '-source.tar')), 'HEAD')
    return source


def framework(binary, name, output):
    target = output / 'Frameworks' / (name + '.framework')
    target.mkdir(parents=True)
    executable = target / name
    shutil.copy2(binary.resolve(strict=True), executable)
    run('xcrun', 'install_name_tool', '-id', '@rpath/' + name + '.framework/' + name, str(executable))
    imports = macho_platform(executable.read_bytes(), 6)
    for dependency in imports:
        if 'libepoxy' in dependency:
            run('xcrun', 'install_name_tool', '-change', dependency,
                '@rpath/epoxy.0.framework/epoxy.0', str(executable))
    run('xcrun', 'install_name_tool', '-add_rpath', '@loader_path/..', str(executable))
    with (target / 'Info.plist').open('wb') as stream:
        plistlib.dump({'CFBundleExecutable': name, 'CFBundleIdentifier': 'com.aghjkshdsj.mypc.engine.' + name,
                      'CFBundleName': name, 'CFBundlePackageType': 'FMWK', 'CFBundleVersion': '1',
                      'CFBundleShortVersionString': '1.0', 'MinimumOSVersion': '26.0',
                      'CFBundleSupportedPlatforms': ['iPhoneOS']}, stream)
    return executable


def build(artifact):
    assert os.uname().sysname == 'Darwin', 'Actual Xcode iOS cross-build host required'
    output = PROJECT / 'out/ios-venus'
    assert not output.exists(), 'Fresh output directory required; never overwrite previous builds'
    output.mkdir(parents=True)
    sdk = capture('xcrun', '--sdk', 'iphoneos', '--show-sdk-path')
    include = output / 'headers'
    headers(artifact / 'MoltenVK-Corresponding-Source.tar.gz', include)
    epoxy = clone('libepoxy', output)
    renderer = clone('virglrenderer', output)
    # Existing Darwin loader supports loose dylibs; add our actual framework form.
    loader = renderer / 'src/venus/vkr_library.c'
    text = loader.read_text(encoding='utf-8')
    old = '   lib->handle = dlopen("libvulkan.dylib", RTLD_NOW | RTLD_LOCAL);'
    assert text.count(old) == 1
    new = ('   lib->handle = dlopen("@rpath/MoltenVK.framework/MoltenVK", RTLD_NOW | RTLD_LOCAL);\n'
           '   if (lib->handle == NULL)\n' + old)
    loader.write_text(text.replace(old, new), encoding='utf-8')
    patch = output / 'ios-framework-loader.patch'
    patch.write_text(capture('git', '-C', str(renderer), 'diff', '--', 'src/venus/vkr_library.c') + '\n', encoding='utf-8')
    prefix = output / 'sysroot'
    flags = ['-target', 'arm64-apple-ios26.0', '-isysroot', sdk, '-I' + str(include)]
    cross = output / 'ios-arm64.cross'
    cross.write_text('\n'.join([
        '[binaries]', "c = ['xcrun', '--sdk', 'iphoneos', 'clang']",
        "objc = ['xcrun', '--sdk', 'iphoneos', 'clang']", "ar = ['xcrun', 'ar']",
        "strip = ['xcrun', 'strip']", "pkg-config = 'pkg-config'",
        '[host_machine]', "system = 'darwin'", "cpu_family = 'aarch64'",
        "cpu = 'arm64'", "endian = 'little'", '[properties]', 'needs_exe_wrapper = true',
        'pkg_config_libdir = ' + repr([str(prefix / 'lib/pkgconfig')]),
        '[built-in options]', 'c_args = ' + repr(flags), 'c_link_args = ' + repr(flags),
        'objc_args = ' + repr(flags), 'objc_link_args = ' + repr(flags), '']), encoding='utf-8')
    common = ['--cross-file', str(cross), '--prefix', str(prefix), '--libdir', 'lib',
              '--buildtype=release', '--default-library=shared', '--wrap-mode=nofallback']
    run('meson', 'setup', str(epoxy / 'build'), str(epoxy), *common,
        '-Dtests=false', '-Ddocs=false', '-Dglx=no', '-Degl=no', '-Dx11=false')
    run('meson', 'compile', '-C', str(epoxy / 'build'), '-j', '3')
    run('meson', 'install', '-C', str(epoxy / 'build'))
    # Venus-only runtime; unused vrend dispatch code has no EGL/GLX backend.
    run('meson', 'setup', str(renderer / 'build'), str(renderer), *common,
        '-Dvenus=true', '-Dneptune=false', '-Dvulkan-dload=true', '-Dvulkan-preload=false',
        '-Dplatforms=[]', '-Dvideo=false', '-Dtests=false', '-Dvtest=false',
        '-Ddrm-renderers=[]', '-Drender-server-mode=thread', '-Drender-server-worker=thread')
    run('meson', 'compile', '-C', str(renderer / 'build'), '-j', '3')
    run('meson', 'install', '-C', str(renderer / 'build'))
    binaries = [framework(prefix / 'lib/libepoxy.0.dylib', 'epoxy.0', output),
                framework(prefix / 'lib/libvirglrenderer.1.dylib', 'virglrenderer.1', output)]
    renderer_symbols = capture('xcrun', 'nm', '-gU', str(binaries[1]))
    required = ['virgl_renderer_init', 'virgl_renderer_get_cap_set', 'virgl_renderer_fill_caps',
                'virgl_renderer_context_create_with_flags', 'virgl_renderer_submit_cmd',
                'virgl_renderer_resource_create_blob', 'virgl_renderer_resource_map', 'virgl_renderer_resource_unmap']
    for name in required:
        assert '_' + name in renderer_symbols, name
    (output / 'renderer-exports.txt').write_text(renderer_symbols + '\n', encoding='utf-8')
    for binary in binaries:
        imports = macho_platform(binary.read_bytes(), 6)
        assert not any('IOKit' in name or 'Hypervisor' in name or '/PrivateFrameworks/' in name for name in imports)
        for dependency in imports:
            if dependency.startswith('/System/Library/') or dependency.startswith('/usr/lib/'):
                continue
            assert dependency.startswith('@rpath/'), dependency
            assert (output / 'Frameworks' / dependency.removeprefix('@rpath/')).is_file(), dependency
    config = (renderer / 'build/config.h').read_text(encoding='utf-8')
    assert '#define ENABLE_VENUS 1' in config and '#define ENABLE_SAME_PROCESS_RENDER_SERVER 1' in config
    assert '#define ENABLE_NEPTUNE 1' not in config and '#define HAVE_EPOXY_EGL_H 1' not in config
    inputs = [cross, patch, output / 'virglrenderer-source.tar', output / 'libepoxy-source.tar']
    receipt = {'schema': 1, 'scope': 'source-built-native-ios-venus-engine-compile-only',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'pins': {name: {'repository': repository, 'commit': revision} for name, (repository, revision) in PINS.items()},
               'vulkan_header_commit': '6aefb8eb95c8e170d0805fd0f2d02832ec1e099a',
               'moltenvk_corresponding_source_sha256': SOURCE_SHA, 'required_exports': required,
               'physical_ios_arm64': True, 'same_process_thread_renderer': True,
               'egl_glx_backend_built': False, 'hardware_virtualization': False,
               'phone_tested': False, 'linux_graphics_verified': False, 'shared_memory_import_verified': False,
               'presentation_verified': False, 'gameplay_verified': False,
               'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in inputs + binaries}}
    receipt_path = output / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'Venus-iOS-Frameworks.tar.gz', 'w:gz') as archive:
        archive.add(output / 'Frameworks', arcname='Frameworks')
    with tarfile.open(output / 'Venus-Corresponding-Source.tar.gz', 'w:gz') as archive:
        for path in inputs + [receipt_path, renderer / 'build/config.h', PROJECT / 'tools/build_venus_ios.py',
                              PROJECT.parent / '.github/workflows/steamos-ios-venus.yml']:
            archive.add(path, arcname=path.name)
        archive.add(artifact / 'MoltenVK-Corresponding-Source.tar.gz', arcname='Vulkan-Headers-and-MoltenVK-Source.tar.gz')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('moltenvk_artifact', type=pathlib.Path)
    build(parser.parse_args().moltenvk_artifact.resolve())
