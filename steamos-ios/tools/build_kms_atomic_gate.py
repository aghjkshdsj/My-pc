#!/usr/bin/env python3
"""Build/boot real ARM DRM atomic controls. Preserve all accepted phone payloads."""
import argparse
import gzip
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import tarfile
import uuid
from build_guest_image_payload import extend_newc
from build_release_channel_gate import parent_inputs, read_init, PARENT_SOURCE, PARENT_RUN, PARENT_FILES
from verify_kms_atomic_gate import validate

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(parent):
    output = PROJECT / 'out/guest-kms-atomic'
    output.mkdir(exist_ok=False)
    payload = output / 'payload'
    payload.mkdir()
    _, inputs = parent_inputs(parent)
    binary = output / 'kms-atomic-gate'
    command = ['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
               '-I/usr/include/libdrm', str(PROJECT / 'Guest/kms_atomic_gate.c'), '-ldrm', '-o', str(binary)]
    subprocess.run(command, check=True)
    assert 'AArch64' in subprocess.check_output(['readelf', '-h', str(binary)], text=True)
    dependencies = [line.split('[')[1].split(']')[0] for line in
                    subprocess.check_output(['readelf', '-d', str(binary)], text=True).splitlines() if '(NEEDED)' in line]
    assert {'libdrm.so.2', 'libc.so.6'} <= set(dependencies) <= {'libdrm.so.2', 'libc.so.6', 'ld-linux-aarch64.so.1'}
    original = gzip.decompress(inputs['initramfs.cpio.gz'])
    init = read_init(original)
    anchor = '/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"'
    assert init.count(anchor) == 1
    insert = '''for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in
    mpc_kms_atomic=1)
        export MPC_KMS_RUN="$nonce"
        /kms-atomic-gate
        kms_status=$?
        /bin/busybox echo "MPC_KMS_EXIT=$kms_status"
        ;;
    esac
done
'''
    init = init.replace(anchor, insert + anchor)
    cpio = extend_newc(original, {'init': (stat.S_IFREG | 0o755, init.encode()),
                                 'kms-atomic-gate': (stat.S_IFREG | 0o755, binary.read_bytes())},
                       additions=('kms-atomic-gate',))
    (payload / 'Image').write_bytes(inputs['Image'])
    (payload / 'initramfs.cpio.gz').write_bytes(gzip.compress(cpio, mtime=0))
    (output / 'init-kms-userspace').write_text(init, encoding='utf-8')
    cases = []
    for present in (True, False):
        nonce = uuid.uuid4().hex
        args = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max',
                '-accel', 'tcg,thread=multi,split-wx=on,tb-size=32', '-smp', '2', '-m', '512',
                '-nodefaults', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
                '-kernel', str(payload / 'Image'), '-initrd', str(payload / 'initramfs.cpio.gz'),
                '-append', 'console=ttyAMA0 rdinit=/init panic=1 mpc_kms_atomic=1 mpc_run=' + nonce, '-no-reboot']
        if present:
            args += ['-device', 'virtio-gpu-pci']
        name = 'atomic-device' if present else 'atomic-missing-device'
        try:
            process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        except subprocess.TimeoutExpired as error:
            (payload / (name + '.log')).write_bytes(error.stdout or b'')
            raise
        (payload / (name + '.log')).write_bytes(process.stdout)
        assert process.returncode == 0, 'Linux engine did not shut down'
        for line in process.stdout.decode('utf-8', errors='strict').splitlines():
            if line.startswith(('MPC_KMS_', 'MPC_LINUX_ABI ', 'MPC_LINUX_EXIT=')):
                print(line, flush=True)
        result = validate(process.stdout.decode('utf-8', errors='strict'), nonce, present)
        cases.append(dict(name=name, engine_exit=process.returncode, serial_sha256=digest(payload / (name + '.log')), **result))
    names = ['Guest/kms_atomic_gate.c', 'tools/build_kms_atomic_gate.py', 'tools/verify_kms_atomic_gate.py',
             'tools/build_release_channel_gate.py', 'tools/build_guest_image_payload.py',
             'tools/make_initramfs.py', 'tools/run_kernel_gate.py', 'tests/test_kms_atomic_gate.py']
    receipt = dict(schema=1, scope='hosted-arm-linux-standard-atomic-api-controls',
                   source_commit=os.environ['GITHUB_SHA'], workflow_run=os.environ['GITHUB_RUN_ID'],
                   parent_source=PARENT_SOURCE, parent_run=PARENT_RUN, parent_files=PARENT_FILES,
                   kernel_unchanged=True, parent_userspace_preserved_except_init=True,
                   compiled_dependencies=dependencies, compiler_command=command,
                   source_files={name: digest(PROJECT / name) for name in names},
                   files={name: dict(bytes=(payload / name).stat().st_size, sha256=digest(payload / name))
                          for name in ('Image', 'initramfs.cpio.gz')}, cases=cases,
                   atomic_api_verified=True, missing_device_rejected=True, physical_iphone=False,
                   native_reader_dependency_verified=False, metal_verified=False, desktop_verified=False,
                   game_fps_verified=False, architecture='QEMU TCG software system emulation; CPU dumb-buffer control only')
    (payload / 'kms-atomic-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'KMS-Atomic-Control-Payload.tar.gz', 'w:gz') as archive:
        archive.add(payload, arcname='payload')
    with tarfile.open(output / 'KMS-Atomic-Corresponding-Source.tar.gz', 'w:gz') as archive:
        archive.add(parent / 'Guest-GPU-Corresponding-Source.tar.gz', arcname='Parent-Guest-GPU-Corresponding-Source.tar.gz')
        for name in names:
            archive.add(PROJECT / name, arcname=name)
        for path in pathlib.Path('/usr/include/libdrm').glob('*.h'):
            archive.add(path, arcname='build-headers/libdrm/' + path.name)
        for name in ('xf86drm.h', 'xf86drmMode.h'):
            archive.add('/usr/include/' + name, arcname='build-headers/' + name)
        archive.add('/usr/share/doc/libdrm-dev/copyright', arcname='build-headers/libdrm-dev-copyright')
        archive.add(output / 'init-kms-userspace', arcname='init-kms-userspace')
        archive.add(payload / 'kms-atomic-receipt.json', arcname='kms-atomic-receipt.json')
        archive.add(PROJECT.parent / '.github/workflows/steamos-kms-atomic-control.yml', arcname='steamos-kms-atomic-control.yml')
    checksums = {name: digest(output / name) for name in
                 ('KMS-Atomic-Control-Payload.tar.gz', 'KMS-Atomic-Corresponding-Source.tar.gz')}
    (payload / 'artifact-checksums.json').write_text(json.dumps(checksums, indent=2) + '\n', encoding='utf-8')
    print('MPC_KMS_ARTIFACTS ' + json.dumps(checksums), flush=True)
    print(json.dumps(dict(scope=receipt['scope'], atomic_api_verified=True,
                         capabilities=cases[0]['capabilities'], physical_iphone=False, metal_verified=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=pathlib.Path)
    build(parser.parse_args().parent.resolve())
