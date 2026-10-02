#!/usr/bin/env python3
"""Source-build only ANGLE EGL/GLES engines for a fresh iOS graphics adapter."""
import hashlib
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import tarfile

from verify_ipa import macho_platform

REVISION = 'ed78ab6e1a37f4f11583a0bd038f22ec91f3ff10'
REPOSITORY = 'https://github.com/utmapp/WebKit.git'
PROJECT = pathlib.Path(__file__).resolve().parents[1]
DIRECTORIES = ['Source/ThirdParty/ANGLE', 'Configurations', 'Tools/ccache']


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def capture(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build():
    assert os.uname().sysname == 'Darwin', 'Actual Xcode iOS cross-build host required'
    output = PROJECT / 'out/ios-angle'
    assert not output.exists(), 'Fresh output required; preserve prior builds'
    output.mkdir(parents=True)
    source = output / 'source'
    source.mkdir()
    run('git', '-C', str(source), 'init', '-q')
    run('git', '-C', str(source), 'remote', 'add', 'origin', REPOSITORY)
    # The source repository contains WebKit; check out only the engine/recipes.
    run('git', '-C', str(source), 'config', 'remote.origin.promisor', 'true')
    run('git', '-C', str(source), 'config', 'remote.origin.partialclonefilter', 'blob:none')
    run('git', '-C', str(source), 'fetch', '--filter=blob:none', '--depth=1', 'origin', REVISION)
    run('git', '-C', str(source), 'sparse-checkout', 'init', '--cone')
    run('git', '-C', str(source), 'sparse-checkout', 'set', *DIRECTORIES)
    run('git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD')
    assert capture('git', '-C', str(source), 'rev-parse', 'HEAD') == REVISION
    root_names = capture('git', '-C', str(source), 'ls-tree', '--name-only', 'HEAD').splitlines()
    licenses = [name for name in root_names if name.upper().startswith(('LICENSE', 'COPYING'))]
    upstream = output / 'ANGLE-Upstream-Source.tar'
    run('git', '-C', str(source), 'archive', '--format=tar', '-o', str(upstream), 'HEAD', '--', *DIRECTORIES, *licenses)
    engine = source / DIRECTORIES[0]
    config = engine / 'Configurations/BaseTarget.xcconfig'
    text = config.read_text(encoding='utf-8')
    # Owner identity uses non-public Metal ownership plumbing. It is unnecessary
    # for an ordinary application and must not enter this engine build.
    assert text.count(' ANGLE_ENABLE_METAL_OWNERSHIP_IDENTITY ') == 1
    # New Clang diagnoses redundant virtual keywords in upstream final classes.
    # Keep that diagnostic visible, but do not promote this style warning to an
    # error. All other upstream warnings-as-errors remain enabled.
    text = text.replace(' ANGLE_ENABLE_METAL_OWNERSHIP_IDENTITY ', ' ')
    text += '\nWARNING_CFLAGS = $(inherited) -Wno-error=unnecessary-virtual-specifier;\n'
    config.write_text(text, encoding='utf-8')
    common = source / 'Configurations/CommonBase.xcconfig'
    text = common.read_text(encoding='utf-8')
    assert text.count('-D_LIBCPP_ENABLE_ASSERTIONS=1') == 5
    common.write_text(text.replace('-D_LIBCPP_ENABLE_ASSERTIONS=1',
                                  '-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE'), encoding='utf-8')
    bitset = engine / 'src/common/bitset_utils.h'
    text = bitset.read_text(encoding='utf-8')
    old = '    if (priv::kDefaultBitSetSize < 64)\n'
    assert text.count(old) == 1
    # The discarded 64-bit branch must not compile a shift by 64 under Clang.
    bitset.write_text(text.replace(old, '    if constexpr (priv::kDefaultBitSetSize < 64)\n'), encoding='utf-8')
    state_cache = engine / 'src/libANGLE/renderer/metal/mtl_state_cache.mm'
    text = state_cache.read_text(encoding='utf-8')
    include = '#include "libANGLE/renderer/metal/mtl_state_cache.h"'
    assert text.count(include) == 1
    text = text.replace(include, include + '\n#include <type_traits>')
    # These four keys contain scalar/bitfield/array state, not owning objects.
    # Preserve upstream's deterministic object bytes, including zeroed padding.
    # Explicit void* expresses intentional object-byte operations to new Clang.
    assert text.count('memset(this, 0, sizeof(*this));') == 4
    assert text.count('memcpy(this, &src, sizeof(*this));') == 12
    for name in ['DepthStencilDesc', 'SamplerDesc', 'RenderPipelineDesc', 'ProvokingVertexComputePipelineDesc']:
        constructor = name + '::' + name + '()\n{\n'
        assert text.count(constructor) == 1
        text = text.replace(constructor, constructor +
                            '    static_assert(std::is_trivially_destructible_v<' + name + '> &&\n'
                            '                  !std::is_polymorphic_v<' + name + '>);\n')
    text = text.replace('memset(this, 0, sizeof(*this));', 'memset(static_cast<void *>(this), 0, sizeof(*this));')
    text = text.replace('memcpy(this, &src, sizeof(*this));', 'memcpy(static_cast<void *>(this), &src, sizeof(*this));')
    state_cache.write_text(text, encoding='utf-8')
    core_types = engine / 'src/libANGLE/angletypes.cpp'
    text = core_types.read_text(encoding='utf-8')
    include = '#include "libANGLE/angletypes.h"'
    assert text.count(include) == 1
    text = text.replace(include, include + '\n#include <type_traits>')
    for name, copies in [('RasterizerState', 2), ('BlendState', 1), ('DepthStencilState', 2), ('SamplerState', 0)]:
        constructor = name + '::' + name + '()\n{\n'
        zero = 'memset(this, 0, sizeof(' + name + '));'
        copy = 'memcpy(this, &other, sizeof(' + name + '));'
        assert text.count(constructor) == text.count(zero) == 1
        assert text.count(copy) == copies
        text = text.replace(constructor, constructor +
                            '    static_assert(std::is_trivially_destructible_v<' + name + '> &&\n'
                            '                  !std::is_polymorphic_v<' + name + '>);\n')
        text = text.replace(zero, zero.replace('(this,', '(static_cast<void *>(this),'))
        text = text.replace(copy, copy.replace('(this,', '(static_cast<void *>(this),'))
    core_types.write_text(text, encoding='utf-8')
    shader_interface = engine / 'src/compiler/translator/ShaderLang.cpp'
    text = shader_interface.read_text(encoding='utf-8')
    include = '#include "GLSLANG/ShaderLang.h"'
    assert text.count(include) == 1
    text = text.replace(include, include + '\n#include <type_traits>')
    # Reviewed shader option/resource structs contain scalar fields, fixed arrays
    # and a non-owning hash-function pointer. Preserve upstream's comparable
    # zeroed padding and its byte-copy semantics, with explicit compiler intent.
    for name in ['ShCompileOptions', 'ShBuiltInResources']:
        constructor = name + '::' + name + '()\n{\n'
        assert text.count(constructor) == 1
        text = text.replace(constructor, constructor +
                            '    static_assert(std::is_trivially_destructible_v<' + name + '> &&\n'
                            '                  !std::is_polymorphic_v<' + name + '>);\n')
    assert text.count('memset(this, 0, sizeof(*this));') == 2
    assert text.count('memcpy(this, &other, sizeof(*this));') == 4
    assert text.count('memset(resources, 0, sizeof(*resources));') == 1
    text = text.replace('memset(this, 0, sizeof(*this));', 'memset(static_cast<void *>(this), 0, sizeof(*this));')
    text = text.replace('memcpy(this, &other, sizeof(*this));', 'memcpy(static_cast<void *>(this), &other, sizeof(*this));')
    text = text.replace('memset(resources, 0, sizeof(*resources));',
                        'memset(static_cast<void *>(resources), 0, sizeof(*resources));')
    shader_interface.write_text(text, encoding='utf-8')
    patch = output / 'public-ios-angle.patch'
    patch.write_text(capture('git', '-C', str(source), 'diff', '--', *DIRECTORIES) + '\n', encoding='utf-8')
    archive = output / 'ANGLE.xcarchive'
    settings = ['CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'USE_INTERNAL_SDK=NO',
                'WEBCORE_LIBRARY_DIR=/usr/local/lib', 'NORMAL_UMBRELLA_FRAMEWORKS_DIR=',
                'IPHONEOS_DEPLOYMENT_TARGET=26.0', 'GCC_OPTIMIZATION_LEVEL=3', 'ANGLE_ALLOWABLE_CLIENTS=']
    command = ['xcodebuild', 'archive', '-project', 'ANGLE.xcodeproj', '-scheme', 'ANGLE',
               '-sdk', 'iphoneos', '-arch', 'arm64', '-configuration', 'Release',
               '-archivePath', str(archive), *settings]
    with (output / 'xcodebuild.log').open('w', encoding='utf-8') as log:
        try:
            run(*command, cwd=engine, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print((output / 'xcodebuild.log').read_text(encoding='utf-8')[-25000:])
            raise
    binaries = []
    for name in ['EGL', 'GLESv2']:
        matches = [p for p in (archive / 'Products').rglob('lib' + name + '.dylib') if p.is_file()]
        assert len(matches) == 1, (name, matches)
        target = output / 'Frameworks' / (name + '.framework')
        target.mkdir(parents=True)
        binary = target / name
        shutil.copy2(matches[0], binary)
        run('xcrun', 'install_name_tool', '-id', '@rpath/' + name + '.framework/' + name, str(binary))
        for dependency in macho_platform(binary.read_bytes(), 6):
            for other in ['EGL', 'GLESv2']:
                if dependency.endswith('/lib' + other + '.dylib'):
                    run('xcrun', 'install_name_tool', '-change', dependency,
                        '@rpath/' + other + '.framework/' + other, str(binary))
        run('xcrun', 'install_name_tool', '-add_rpath', '@loader_path/..', str(binary))
        with (target / 'Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleExecutable': name, 'CFBundleIdentifier': 'com.aghjkshdsj.mypc.engine.' + name,
                          'CFBundleName': name, 'CFBundlePackageType': 'FMWK', 'CFBundleVersion': '1',
                          'CFBundleShortVersionString': '1.0', 'MinimumOSVersion': '26.0',
                          'CFBundleSupportedPlatforms': ['iPhoneOS']}, stream)
        binaries.append(binary)
    required = {'EGL': ['eglGetProcAddress', 'eglGetPlatformDisplay', 'eglInitialize', 'eglCreateContext'],
                'GLESv2': ['glGetString', 'glDrawArrays', 'glReadPixels', 'glFenceSync']}
    imports = {}
    for binary in binaries:
        symbols = capture('xcrun', 'nm', '-gU', str(binary))
        for name in required[binary.name]:
            assert '_' + name in symbols, name
        (output / (binary.name + '-exports.txt')).write_text(symbols + '\n', encoding='utf-8')
        dependencies = macho_platform(binary.read_bytes(), 6)
        imports[binary.name] = dependencies
        assert not any('IOKit' in name or 'Hypervisor' in name or '/PrivateFrameworks/' in name for name in dependencies)
        for dependency in dependencies:
            if dependency.startswith(('/System/Library/', '/usr/lib/')):
                continue
            assert dependency.startswith('@rpath/'), dependency
            assert (output / 'Frameworks' / dependency.removeprefix('@rpath/')).is_file(), dependency
    assert '/System/Library/Frameworks/Metal.framework/Metal' in imports['GLESv2']
    receipt = {'schema': 1, 'scope': 'source-built-native-ios-angle-engine-compile-only',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'engine_repository': REPOSITORY, 'engine_commit': REVISION, 'source_paths': DIRECTORIES,
               'source_application_reused': False, 'xcode_version': capture('xcodebuild', '-version'),
               'sdk_version': capture('xcrun', '--sdk', 'iphoneos', '--show-sdk-version'),
               'command': command, 'public_ios_sdk': True, 'metal_owner_identity_enabled': False,
               'physical_ios_arm64': True, 'metal_backend_compiled': True,
               'opengl_es_backend_compiled': True, 'phone_tested': False,
               'linux_graphics_verified': False, 'metal_runtime_verified': False,
               'presentation_verified': False, 'gameplay_verified': False,
               'required_exports': required, 'imports': imports,
               'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)}
                         for p in binaries + [upstream, patch]}}
    receipt_path = output / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'ANGLE-iOS-Frameworks.tar.gz', 'w:gz') as package:
        package.add(output / 'Frameworks', arcname='Frameworks')
        package.add(engine / 'include', arcname='include')
    with tarfile.open(output / 'ANGLE-Corresponding-Source.tar.gz', 'w:gz') as package:
        for path in [upstream, patch, receipt_path, PROJECT / 'tools/build_angle_ios.py',
                     PROJECT.parent / '.github/workflows/steamos-ios-angle.yml']:
            package.add(path, arcname=path.name)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    build()
