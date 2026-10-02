#!/usr/bin/env python3
"""Assemble a fresh Mesa+runtime guest test, then boot real missing-3D controls."""
import argparse
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import tarfile
import uuid

from make_initramfs import record
from run_gpu_kernel_gate import validate as validate_kernel
from stage_guest_runtime import digest, stage

PROJECT = pathlib.Path(__file__).resolve().parents[1]
MESA_RUN = 37074804870
MESA_SOURCE = '9ddc641f25d83a230affb90c7e59174a041bde30'
KERNEL_SOURCE = '6ab4df9f78ec307e026f378658673efa3ebeeec2'
KERNEL_FILES = {'Image': '5945ac10f6eee547435c617f75820bc0d248592f559d0a1e25005b73f9c4b9c0',
                'initramfs.cpio.gz': '50ded9b52f5a975d69ec086da8fe324f65fcdf84a830ea70571c58d911ec6618'}


def parse_newc(data):
    """Bounded regular seed entries only; never extract the cpio onto the host."""
    assert len(data) < 128 * 1024 * 1024
    offset, entries = 0, {}
    while True:
        assert data[offset:offset + 6] == b'070701', 'Invalid newc magic/truncation'
        raw = data[offset + 6:offset + 110]
        assert len(raw) == 104
        fields = [int(raw[i:i + 8], 16) for i in range(0, 104, 8)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        assert 1 < namesize < 4096 and size < 64 * 1024 * 1024
        start = offset + 110
        encoded = data[start:start + namesize]
        assert len(encoded) == namesize and encoded[-1:] == b'\0' and b'\0' not in encoded[:-1]
        name = encoded[:-1].decode('utf-8', errors='strict')
        position = (start + namesize + 3) & ~3
        content = data[position:position + size]
        assert len(content) == size
        offset = (position + size + 3) & ~3
        if name == 'TRAILER!!!':
            assert size == 0 and not any(data[offset:])
            return entries
        path = pathlib.PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and name not in entries
        assert stat.S_IFMT(mode) in [stat.S_IFDIR, stat.S_IFREG, stat.S_IFCHR]
        entries[name] = (mode, content, fields[9], fields[10])


def build(kernel_artifact, mesa_artifact):
    output = PROJECT / 'out/guest-gpu-payload'
    assert not output.exists(), 'Fresh payload directory required'
    output.mkdir()
    kernel = output / 'kernel-input'
    kernel.mkdir()
    with tarfile.open(kernel_artifact / 'GPU-Kernel-Payload.tar.gz') as archive:
        for member in archive.getmembers():
            assert member.isfile() and member.name in [*KERNEL_FILES, 'payload-receipt.json', 'gpu-kernel-test.json']
            assert member.size < 128 * 1024 * 1024
            path = kernel / member.name
            assert not path.exists()
            path.write_bytes(archive.extractfile(member).read())
    for name, sha in KERNEL_FILES.items():
        assert digest(kernel / name) == sha
    kernel_receipt = json.loads((kernel / 'gpu-kernel-test.json').read_text(encoding='utf-8'))
    assert kernel_receipt['source_commit'] == KERNEL_SOURCE and int(kernel_receipt['workflow_run']) == 37067848259
    assert kernel_receipt['scope'] == 'hosted-arm-linux-virtio-gpu-kernel-device-test'
    mesa_receipt = json.loads((mesa_artifact / 'receipt.json').read_text(encoding='utf-8'))
    assert mesa_receipt['scope'] == 'source-built-linux-arm64-guest-mesa-userspace-compile-only'
    assert mesa_receipt['source_commit'] == MESA_SOURCE and int(mesa_receipt['workflow_run']) == MESA_RUN
    seed = parse_newc(gzip.decompress((kernel / 'initramfs.cpio.gz').read_bytes()))
    assert set(seed) == {'dev', 'proc', 'sys', 'bin', 'bin/busybox', 'mpc-abi', 'mpc-gpu-kernel', 'init', 'dev/console'}
    root = output / 'root'
    root.mkdir()
    for name in ['bin/busybox', 'mpc-abi', 'mpc-gpu-kernel']:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(seed[name][1])
        target.chmod(0o755)
    temporary = output / 'mesa-input'
    temporary.mkdir()
    with tarfile.open(mesa_artifact / 'Guest-Mesa-Userspace.tar.gz') as archive:
        total = 0
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[0] == 'staging' or member.name in [
                'vk-gate', 'vertex.spv', 'fragment.spv', 'receipt.json', 'external-linux-packages.tsv']
            assert member.isdir() or member.isfile() or member.issym()
            total += member.size
            assert total < 256 * 1024 * 1024
            if member.issym():
                link = pathlib.PurePosixPath(member.linkname)
                assert not link.is_absolute() and '..' not in link.parts
        archive.extractall(temporary, filter='data')
    for name, expected in mesa_receipt['files'].items():
        if name.startswith('staging/') or name in ['vk-gate', 'vertex.spv', 'fragment.spv']:
            path = temporary / name
            assert path.is_file() and not path.is_symlink()
            assert path.stat().st_size == expected['bytes'] and digest(path) == expected['sha256'], name
    shutil.copytree(temporary / 'staging', root, dirs_exist_ok=True, symlinks=True)
    for name in ['vk-gate', 'vertex.spv', 'fragment.spv']:
        shutil.copy2(temporary / name, root / name)
    manifests = list((root / 'usr/share/vulkan/icd.d').glob('virtio*.json'))
    assert len(manifests) == 1 and manifests[0].name == 'virtio_icd.aarch64.json'
    runtime = stage(root, output / 'runtime-source')
    shutil.copy2(PROJECT / 'Guest/init-gpu-userspace', root / 'init')
    (root / 'init').chmod(0o755)
    for name in ['dev', 'proc', 'sys', 'tmp']:
        (root / name).mkdir(exist_ok=True)
    data = b''
    inventory = {}
    for inode, path in enumerate(sorted(root.rglob('*')), 1):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            mode, content = stat.S_IFLNK | 0o777, os.readlink(path).encode()
        elif path.is_dir():
            mode, content = stat.S_IFDIR | 0o755, b''
        else:
            mode, content = stat.S_IFREG | (0o755 if path.read_bytes()[:4] == b'\x7fELF' or relative == 'init' else 0o644), path.read_bytes()
        data += record(relative, mode, content, inode=inode)
        inventory[relative] = {'mode': mode, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    data += record('dev/console', stat.S_IFCHR | 0o600, inode=10000, rdevmajor=5, rdevminor=1)
    data += record('TRAILER!!!', 0, inode=10001)
    payload = output / 'payload'
    payload.mkdir()
    shutil.copy2(kernel / 'Image', payload / 'Image')
    (payload / 'initramfs.cpio.gz').write_bytes(gzip.compress(data, mtime=0))
    cases = []
    for device in [True, False]:
        nonce = uuid.uuid4().hex
        command = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max', '-accel',
                   'tcg,thread=multi,split-wx=on,tb-size=32', '-smp', '2', '-m', '512', '-nodefaults',
                   '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-kernel', str(payload / 'Image'),
                   '-initrd', str(payload / 'initramfs.cpio.gz'), '-append',
                   'console=ttyAMA0 rdinit=/init panic=1 mpc_run=' + nonce, '-no-reboot']
        if device:
            command += ['-device', 'virtio-gpu-pci']
        process = subprocess.run(command, capture_output=True, text=True, timeout=180)
        serial = process.stdout + process.stderr
        (payload / ('2d-device.log' if device else 'missing-device.log')).write_text(serial, encoding='utf-8')
        print(serial)
        assert process.returncode == 0
        result = validate_kernel(serial, nonce, device)
        assert serial.splitlines().count('MPC_GPU_GUEST_RUN=' + nonce) == 1
        assert 'MPC_VK_DIAGNOSTIC' not in serial and 'MPC_VK_REJECTED' not in serial
        assert serial.splitlines().count('MPC_GPU_GUEST_EXIT=3') == 1
        assert 'Vulkan call failed: vkEnumeratePhysicalDevices(' in serial
        cases.append({'run': nonce, 'has_2d_device': device, 'command': command,
                      'engine_exit': process.returncode, 'serial_sha256': hashlib.sha256(serial.encode()).hexdigest(),
                      'vulkan_missing_3d_rejected': True, **result})
    receipt = {'schema': 1, 'scope': 'linux-arm64-graphics-payload-missing-3d-boot-controls',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'kernel_input': kernel_receipt, 'mesa_input_source': MESA_SOURCE, 'mesa_input_run': MESA_RUN,
               'runtime': runtime, 'inventory': inventory, 'cases': cases,
               'runtime_dependency_closure_verified': True, 'linux_runtime_boot_verified': True,
               'guest_shader_verified': False, 'phone_tested': False, 'metal_verified': False,
               'presentation_verified': False, 'steamos_verified': False, 'gameplay_verified': False,
               'files': {name: {'bytes': (payload / name).stat().st_size, 'sha256': digest(payload / name)}
                         for name in ['Image', 'initramfs.cpio.gz']}}
    (payload / 'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    with tarfile.open(output / 'Guest-GPU-Payload.tar.gz', 'w:gz') as archive:
        archive.add(payload, arcname='payload')
    with tarfile.open(output / 'Guest-GPU-Corresponding-Source.tar.gz', 'w:gz') as archive:
        # APT's root-owned lock is not corresponding source. Retain the source
        # packages/configuration and readable signed/index metadata explicitly.
        source = output / 'runtime-source'
        for name in ['packages', 'apt-sourceparts']:
            archive.add(source / name, arcname='runtime-source/' + name)
        for path in sorted((source / 'apt-lists').iterdir()):
            if path.is_file() and path.name != 'lock':
                archive.add(path, arcname='runtime-source/apt-lists/' + path.name)
        archive.add(temporary / 'external-linux-packages.tsv', arcname='Mesa-build-distribution-packages.tsv')
        archive.add(payload / 'payload-receipt.json', arcname='payload-receipt.json')
        archive.add(kernel_artifact / 'GPU-Kernel-Corresponding-Source.tar.gz', arcname='GPU-Kernel-Corresponding-Source.tar.gz')
        archive.add(mesa_artifact / 'Guest-Mesa-Corresponding-Source.tar.gz', arcname='Guest-Mesa-Corresponding-Source.tar.gz')
        for name in ['tools/build_guest_gpu_payload.py', 'tools/stage_guest_runtime.py', 'tools/make_initramfs.py',
                     'tools/run_gpu_kernel_gate.py', 'tools/run_kernel_gate.py', 'Guest/init-gpu-userspace']:
            archive.add(PROJECT / name, arcname=name)
        archive.add(PROJECT.parent / '.github/workflows/steamos-guest-gpu-payload.yml', arcname='steamos-guest-gpu-payload.yml')
    # Print a compact result; the complete receipt includes all source versions
    # and inventory, and is retained in the actual artifact.
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['inventory', 'kernel_input', 'runtime', 'cases']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel_artifact', type=pathlib.Path)
    parser.add_argument('mesa_artifact', type=pathlib.Path)
    args = parser.parse_args()
    build(args.kernel_artifact.resolve(), args.mesa_artifact.resolve())
