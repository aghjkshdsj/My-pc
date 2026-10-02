#!/usr/bin/env python3
"""Build source-pinned ARM Linux virgl/Venus userspace, not an OS or phone proof."""
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import tarfile
import urllib.request

PROJECT = pathlib.Path(__file__).resolve().parents[1]
VERSION = '26.2.2'
SOURCE_SHA = 'eeb29ca7e56cfaa8e8a79538dcf834e3b18e501c31bef5145e959ea437cc4216'


def run(*arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def capture(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def arm_elf(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20], 'little') == 183, path


def build():
    assert platform.system() == 'Linux' and platform.machine() == 'aarch64'
    output = PROJECT / 'out/guest-mesa'
    assert not output.exists(), 'Fresh guest userspace build required'
    output.mkdir(parents=True)
    upstream = output / ('mesa-' + VERSION + '.tar.xz')
    url = 'https://archive.mesa3d.org/' + upstream.name
    with urllib.request.urlopen(url, timeout=120) as response, upstream.open('xb') as stream:
        while data := response.read(1024 * 1024):
            stream.write(data)
    assert digest(upstream) == SOURCE_SHA
    with tarfile.open(upstream) as archive:
        archive.extractall(output, filter='data')
    source = output / ('mesa-' + VERSION)
    directory = output / 'build'
    staging = output / 'staging'
    options = ['--prefix=/usr', '--libdir=lib', '--buildtype=release', '--wrap-mode=nofallback',
               '-Dgallium-drivers=virgl', '-Dvulkan-drivers=virtio', '-Dplatforms=[]',
               '-Dglx=disabled', '-Degl=enabled', '-Dgbm=enabled', '-Dglvnd=disabled',
               '-Dllvm=disabled', '-Dgallium-rusticl=false', '-Dvideo-codecs=[]',
               '-Dvalgrind=disabled', '-Dlibunwind=disabled', '-Dzstd=disabled',
               '-Dbuild-tests=false']
    run('meson', 'setup', str(directory), str(source), *options)
    run('meson', 'compile', '-C', str(directory), '-j', '3')
    run('meson', 'install', '-C', str(directory), '--destdir', str(staging))
    # These are guest Linux libraries. Never package them as native iOS engines.
    venus = staging / 'usr/lib/libvulkan_virtio.so'
    arm_elf(venus)
    for name in ['EGL', 'GLESv2', 'gbm']:
        arm_elf((staging / 'usr/lib' / ('lib' + name + '.so')).resolve(strict=True))
    # This release installs one versioned Gallium DSO, without old *_dri aliases.
    gallium = staging / ('usr/lib/libgallium-' + VERSION + '.so')
    arm_elf(gallium)
    settings = {x['name']: x['value'] for x in json.loads(
        (directory / 'meson-info/intro-buildoptions.json').read_text(encoding='utf-8'))}
    assert settings['gallium-drivers'] == ['virgl'] and settings['vulkan-drivers'] == ['virtio']
    commands = json.loads((directory / 'compile_commands.json').read_text(encoding='utf-8'))
    target_commands = [x for x in commands if x['file'].endswith('/dri_target.c')]
    assert len(target_commands) == 1
    command = target_commands[0].get('command') or ' '.join(target_commands[0]['arguments'])
    assert '-DGALLIUM_VIRGL' in command, 'Unified driver must include virgl, not its stub'
    assert '_mesa_glapi_get_proc_address' in capture('nm', '-D', '--defined-only', str(gallium))
    manifests = list((staging / 'usr/share/vulkan/icd.d').glob('virtio*.json'))
    assert len(manifests) == 1
    icd = json.loads(manifests[0].read_text(encoding='utf-8'))
    assert icd['ICD']['library_path'] == '/usr/lib/libvulkan_virtio.so', icd
    executable = output / 'vk-gate'
    run('gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        str(PROJECT / 'Guest/vk_gate.c'), '-lvulkan', '-o', str(executable))
    arm_elf(executable)
    for stage, filename in [('vert', 'vertex.spv'), ('frag', 'fragment.spv')]:
        run('glslangValidator', '-V', '--target-env', 'vulkan1.1',
            str(PROJECT / ('Guest/vk_gate.' + stage)), '-o', str(output / filename))
        run('spirv-val', '--target-env', 'vulkan1.1', str(output / filename))
    # The hosted build has no virtio GPU. Pin the exact new driver and require
    # failure before any graphics receipt; a system software ICD must not pass.
    assert not pathlib.Path('/dev/dri').exists(), 'Dedicated missing-GPU test host required'
    missing_icd = output / 'missing-device-icd.json'
    missing = json.loads(json.dumps(icd))
    missing['ICD']['library_path'] = str(venus)
    missing_icd.write_text(json.dumps(missing) + '\n', encoding='utf-8')
    environment = dict(os.environ, VK_DRIVER_FILES=str(missing_icd),
                       LD_LIBRARY_PATH=str(staging / 'usr/lib'))
    environment.pop('VN_DEBUG', None)
    result = subprocess.run([str(executable), str(output / 'vertex.spv'), str(output / 'fragment.spv')],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 3 and 'Vulkan call failed:' in result.stderr
    assert 'MPC_VK_DIAGNOSTIC' not in result.stdout and 'MPC_VK_REJECTED' not in result.stdout
    (output / 'missing-device.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    # External Linux runtime libraries/loader remain dependencies, not secretly
    # included in this archive. Their exact packages are recorded for payload work.
    runtime = [p for p in staging.rglob('*') if p.is_file() and not p.is_symlink()
               and p.open('rb').read(4) == b'\x7fELF']
    dependencies = {p.name: capture('ldd', str(p)) for p in runtime + [executable]}
    packages = capture('dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n')
    (output / 'external-linux-packages.tsv').write_text(packages + '\n', encoding='utf-8')
    binaries = [p for p in staging.rglob('*') if p.is_file() and not p.is_symlink()]
    receipt = {'schema': 1, 'scope': 'source-built-linux-arm64-guest-mesa-userspace-compile-only',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'upstream_url': url, 'upstream_sha256': SOURCE_SHA, 'mesa_version': VERSION,
               'meson_options': options, 'linux_arm64': True, 'virgl_compiled': True, 'venus_compiled': True,
               'missing_device_exit': result.returncode, 'external_linux_dependencies': dependencies,
               'kernel_boot_tested': False, 'phone_tested': False, 'guest_shader_verified': False,
               'metal_verified': False, 'presentation_verified': False, 'steamos_verified': False,
               'gameplay_verified': False,
               'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)}
                         for p in [upstream, executable, output / 'vertex.spv', output / 'fragment.spv'] + binaries}}
    receipt_path = output / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'Guest-Mesa-Userspace.tar.gz', 'w:gz') as archive:
        archive.add(staging, arcname='staging')
        for name in ['vk-gate', 'vertex.spv', 'fragment.spv', 'receipt.json', 'external-linux-packages.tsv']:
            archive.add(output / name, arcname=name)
    with tarfile.open(output / 'Guest-Mesa-Corresponding-Source.tar.gz', 'w:gz') as archive:
        for path in [upstream, receipt_path, directory / 'meson-info/intro-buildoptions.json',
                     directory / 'meson-logs/meson-log.txt', PROJECT / 'tools/build_guest_mesa.py',
                     PROJECT / 'Guest/vk_gate.c', PROJECT / 'Guest/renderer_classification.h',
                     PROJECT / 'Guest/vk_gate.vert', PROJECT / 'Guest/vk_gate.frag',
                     PROJECT.parent / '.github/workflows/steamos-guest-mesa.yml']:
            archive.add(path, arcname=path.name)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    build()
