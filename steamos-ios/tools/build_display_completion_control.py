#!/usr/bin/env python3
"""Boot actual standard Linux fences with injected delayed/error/missing responses."""
import argparse
import gzip
import hashlib
import json
import os
import pathlib
import selectors
import stat
import subprocess
import tarfile
import time
import uuid
from build_guest_image_payload import extend_newc
from build_release_channel_gate import parent_inputs, read_init, PARENT_FILES, PARENT_RUN, PARENT_SOURCE
from verify_display_completion_control import validate

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def boot(payload, engine, case, output):
    nonce = uuid.uuid4().hex
    properties = 'virtio-gpu-pci,xres=1280,yres=720,x-mpc-control-delay-ms=1000'
    if case == 'error': properties += ',x-mpc-control-fail-at=2'
    if case == 'missing': properties += ',x-mpc-control-missing-at=2'
    args = [str(engine), '-machine', 'virt', '-cpu', 'max', '-accel', 'tcg,thread=multi,split-wx=on,tb-size=32',
            '-smp', '2', '-m', '512', '-nodefaults', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
            '-kernel', str(payload / 'Image'), '-initrd', str(payload / 'initramfs.cpio.gz'), '-no-reboot',
            '-device', properties, '-append', 'console=ttyAMA0 rdinit=/init panic=1 '
            'virtio_gpu.mpc_native_display_fences=1 mpc_completion=' + case + ' mpc_run=' + nonce]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    serial = bytearray(); pending = bytearray(); terminated = False
    deadline = time.monotonic() + 180
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while time.monotonic() < deadline:
            ready = selector.select(0.5)
            if not ready:
                if process.poll() is not None: break
                continue
            data = os.read(process.stdout.fileno(), 65536)
            if not data: break
            serial.extend(data); pending.extend(data)
            assert len(serial) < 8 * 1024 * 1024
            while b'\n' in pending:
                raw, _, pending = pending.partition(b'\n'); pending = bytearray(pending)
                line = raw.decode('utf-8', errors='strict').rstrip('\r')
                if line.startswith(('MPC_COMPLETION_', 'MPC_LINUX_ABI ', 'MPC_LINUX_EXIT=')):
                    print(line, flush=True)
                if case == 'missing' and line.startswith('MPC_COMPLETION_RESULT '):
                    # Validate the pending receipt before terminating; invalid rows never pass.
                    validate(serial.decode(), nonce, case, -9)
                    process.kill(); terminated = True
            if terminated: break
        assert time.monotonic() < deadline, 'Control boot deadline'
        trailing, _ = process.communicate(timeout=10); serial.extend(trailing)
    finally:
        selector.close()
        if process.poll() is None: process.kill(); process.communicate()
        (output / (case + '.log')).write_bytes(serial)
    if case == 'missing' and not terminated:
        raise ValueError('Missing-response retention was not observed')
    return dict(serial_sha256=digest(output / (case + '.log')), engine_command=args,
                **validate(serial.decode(), nonce, case, process.returncode))


def build(parent, kernel, engine_root):
    output = PROJECT / 'out/display-completion-control'
    output.mkdir(exist_ok=False); payload = output / 'payload'; payload.mkdir()
    _, inputs = parent_inputs(parent)
    kernel_image = kernel / 'payload/Image'
    patch = json.loads((kernel / 'display-patch/patch-receipt.json').read_text())
    assert patch['scope'] == 'linux-exact-display-response-completion-source'
    binary = output / 'kms-completion-control'
    command = ['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-I/usr/include/libdrm',
               str(PROJECT / 'Guest/kms_completion_control.c'), '-ldrm', '-o', str(binary)]
    subprocess.run(command, check=True)
    assert 'AArch64' in subprocess.check_output(['readelf', '-h', str(binary)], text=True)
    dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
    dependencies = [line.split('[')[1].split(']')[0] for line in dynamic.splitlines() if '(NEEDED)' in line]
    assert {'libdrm.so.2', 'libc.so.6'} <= set(dependencies) <= {'libdrm.so.2', 'libc.so.6', 'ld-linux-aarch64.so.1'}
    original = gzip.decompress(inputs['initramfs.cpio.gz']); init = read_init(original)
    anchor = '/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"'
    assert init.count(anchor) == 1
    insert = '''for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in
    mpc_completion=*)
        export MPC_KMS_RUN="$nonce"
        export MPC_COMPLETION_CASE="${token#mpc_completion=}"
        /kms-completion-control
        completion_status=$?
        /bin/busybox echo "MPC_COMPLETION_EXIT=$completion_status"
        ;;
    esac
done
'''
    init = init.replace(anchor, insert + anchor)
    cpio = extend_newc(original, {'init': (stat.S_IFREG | 0o755, init.encode()),
                       'kms-completion-control': (stat.S_IFREG | 0o755, binary.read_bytes())},
                       additions=('kms-completion-control',))
    (payload / 'Image').write_bytes(kernel_image.read_bytes())
    assert digest(payload / 'Image') != PARENT_FILES['Image'], 'Must test the actual modified kernel'
    (payload / 'initramfs.cpio.gz').write_bytes(gzip.compress(cpio, mtime=0))
    engine = engine_root / 'build/qemu-system-aarch64'
    cases = [boot(payload, engine, name, payload) for name in ('delayed', 'error', 'missing')]
    receipt = dict(schema=1, scope='hosted-arm-linux-exact-display-response-controls',
                   source_commit=os.environ['GITHUB_SHA'], workflow_run=os.environ['GITHUB_RUN_ID'],
                   parent_source=PARENT_SOURCE, parent_run=PARENT_RUN, parent_files=PARENT_FILES,
                   kernel_unchanged=False, opt_in='virtio_gpu.mpc_native_display_fences=1',
                   cases=cases, kernel_patch=patch, dependencies=dependencies, compiler_command=command,
                   files={name: dict(bytes=(payload / name).stat().st_size, sha256=digest(payload / name))
                          for name in ('Image', 'initramfs.cpio.gz')}, engine_sha256=digest(engine),
                   native_reader_dependency_verified=False, metal_verified=False, phone_verified=False,
                   compositor_verified=False, game_fps_verified=False)
    (payload / 'display-completion-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'Display-Completion-Control-Payload.tar.gz', 'w:gz') as archive:
        archive.add(payload, arcname='payload')
    with tarfile.open(output / 'Display-Completion-Control-Corresponding-Source.tar.gz', 'w:gz') as archive:
        for path in (parent / 'Guest-GPU-Corresponding-Source.tar.gz',
                     kernel / 'Display-Completion-Kernel-Corresponding-Source.tar.gz',
                     engine_root / 'Display-Fault-QEMU-Corresponding-Source.tar.gz'):
            archive.add(path, arcname=path.name)
        for name in ('Guest/kms_completion_control.c', 'Guest/kms_atomic_gate.c',
                     'tools/build_display_completion_control.py', 'tools/verify_display_completion_control.py',
                     'tools/build_release_channel_gate.py', 'tools/build_guest_image_payload.py',
                     'tools/make_initramfs.py', 'tools/run_kernel_gate.py', 'tests/test_display_completion_control.py'):
            archive.add(PROJECT / name, arcname=name)
        archive.add(PROJECT.parent / '.github/workflows/steamos-display-completion-control.yml', arcname='steamos-display-completion-control.yml')
        archive.add(payload / 'display-completion-receipt.json', arcname='display-completion-receipt.json')
    print('MPC_COMPLETION_ARTIFACTS ' + json.dumps({p.name: digest(p) for p in output.glob('*.tar.gz')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=pathlib.Path); parser.add_argument('kernel', type=pathlib.Path)
    parser.add_argument('engine', type=pathlib.Path)
    args = parser.parse_args()
    build(args.parent.resolve(), args.kernel.resolve(), args.engine.resolve())
