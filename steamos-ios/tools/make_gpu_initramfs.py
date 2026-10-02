#!/usr/bin/env python3
"""Separate deterministic graphics kernel payload; preserve the CPU baseline."""
import argparse
import gzip
import hashlib
import json
import pathlib
import stat

from make_initramfs import assert_static_arm64, record

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def build(kernel, busybox, abi, probe, output):
    image = kernel.read_bytes()
    assert image[56:60] == b'ARMd', 'Expected uncompressed ARM64 Linux Image'
    for executable in [busybox, abi, probe]:
        assert_static_arm64(executable.read_bytes())
    entries = [(name, stat.S_IFDIR | 0o755, b'') for name in ['dev', 'proc', 'sys', 'bin']]
    entries += [('bin/busybox', stat.S_IFREG | 0o755, busybox.read_bytes()),
                ('mpc-abi', stat.S_IFREG | 0o755, abi.read_bytes()),
                ('mpc-gpu-kernel', stat.S_IFREG | 0o755, probe.read_bytes()),
                ('init', stat.S_IFREG | 0o755, (PROJECT / 'Guest/init-gpu-kernel').read_bytes())]
    data = b''.join(record(name, mode, content, i + 1) for i, (name, mode, content) in enumerate(entries))
    data += record('dev/console', stat.S_IFCHR | 0o600, inode=30, rdevmajor=5, rdevminor=1)
    data += record('TRAILER!!!', 0, inode=31)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'Image').write_bytes(image)
    (output / 'initramfs.cpio.gz').write_bytes(gzip.compress(data, mtime=0))
    receipt = {'schema': 1, 'kind': 'disposable-linux-virtio-gpu-kernel-gate',
               'steamos': False, 'phone_tested': False, 'gpu_shader_verified': False,
               'metal_verified': False, 'presentation_verified': False,
               'files': {name: {'bytes': (output / name).stat().st_size,
                                'sha256': hashlib.sha256((output / name).read_bytes()).hexdigest()}
                         for name in ['Image', 'initramfs.cpio.gz']},
               'sources': {name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
                           for name in ['Guest/abi_probe.c', 'Guest/gpu_kernel_probe.c', 'Guest/init-gpu-kernel']}}
    (output / 'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel', 'busybox', 'abi', 'probe', 'output']:
        parser.add_argument(name, type=pathlib.Path)
    args = parser.parse_args()
    build(args.kernel, args.busybox, args.abi, args.probe, args.output)
