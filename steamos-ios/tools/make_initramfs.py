#!/usr/bin/env python3
"""Deterministic fresh newc initramfs; no extraction or mounted old disks."""
import argparse
import gzip
import hashlib
import json
import pathlib
import stat
import struct

def assert_static_arm64(data):
    assert data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    for i in range(count):
        assert struct.unpack_from('<I', data, offset + i * size)[0] != 3, 'PT_INTERP in initramfs program'

def record(name, mode, data=b'', inode=1, rdevmajor=0, rdevminor=0):
    encoded = name.encode() + b'\0'
    fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, rdevmajor, rdevminor, len(encoded), 0]
    header = b'070701' + ''.join(f'{x:08x}' for x in fields).encode()
    prefix = header + encoded
    return prefix + b'\0' * (-len(prefix) % 4) + data + b'\0' * (-len(data) % 4)

def build(kernel, busybox, abi, output):
    image = kernel.read_bytes()
    if image[:2] == b'\x1f\x8b': image = gzip.decompress(image)
    assert len(image) > 64 and image[56:60] == b'ARMd', 'Expected ARM64 Linux Image'
    for path in [busybox, abi]: assert_static_arm64(path.read_bytes())
    entries = [('dev', stat.S_IFDIR | 0o755, b''), ('proc', stat.S_IFDIR | 0o755, b''),
               ('bin', stat.S_IFDIR | 0o755, b''),
               ('bin/busybox', stat.S_IFREG | 0o755, busybox.read_bytes()),
               ('mpc-abi', stat.S_IFREG | 0o755, abi.read_bytes()),
               ('init', stat.S_IFREG | 0o755, (pathlib.Path(__file__).resolve().parents[1] / 'Guest/init').read_bytes())]
    data = b''.join(record(name, mode, content, i + 1) for i, (name, mode, content) in enumerate(entries))
    data += record('dev/console', stat.S_IFCHR | 0o600, inode=20, rdevmajor=5, rdevminor=1)
    data += record('TRAILER!!!', 0, inode=21)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'Image').write_bytes(image)
    (output / 'initramfs.cpio.gz').write_bytes(gzip.compress(data, mtime=0))
    receipt = {'schema': 1, 'kind': 'disposable-linux-abi-gate', 'steamos': False,
               'files': {name: {'bytes': (output/name).stat().st_size, 'sha256': hashlib.sha256((output/name).read_bytes()).hexdigest()}
                         for name in ['Image', 'initramfs.cpio.gz']},
               'abi_source_sha256': hashlib.sha256((pathlib.Path(__file__).resolve().parents[1] / 'Guest/abi_probe.c').read_bytes()).hexdigest()}
    (output/'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['kernel', 'busybox', 'abi', 'output']: parser.add_argument(name, type=pathlib.Path)
    args = parser.parse_args()
    build(args.kernel, args.busybox, args.abi, args.output)
