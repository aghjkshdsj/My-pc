#!/usr/bin/env python3
"""Verify the produced native app, its identity, inputs and absence of a VM."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import struct
import sys
import zipfile


def macho(data, filetype):
    assert len(data) >= 32, 'Truncated Mach-O'
    magic, cpu, _, kind, commands, command_bytes, _, _ = struct.unpack_from('<8I', data)
    assert magic == 0xfeedfacf, 'Expected little-endian 64-bit Mach-O'
    assert cpu == 0x0100000c, 'Expected ARM64 host'
    assert kind == filetype, 'Unexpected Mach-O file type'
    assert 32 + command_bytes <= len(data), 'Truncated Mach-O load commands'
    position = 32
    platforms, libraries = [], []
    for _ in range(commands):
        command, length = struct.unpack_from('<II', data, position)
        assert length >= 8 and position + length <= 32 + command_bytes, 'Invalid Mach-O load command'
        if command == 0x32:
            assert length >= 24
            platforms.append(struct.unpack_from('<I', data, position + 8)[0])
        if command in (0xc, 0x80000018, 0x8000001f):
            assert length >= 24
            offset = struct.unpack_from('<I', data, position + 8)[0]
            assert 24 <= offset < length
            libraries.append(data[position + offset:position + length].split(b'\0', 1)[0].decode())
        position += length
    assert position == 32 + command_bytes
    assert platforms == [2], 'Expected Mach-O iOS platform'
    return libraries


def verify(path, lock_path):
    lock = json.loads(Path(lock_path).read_text())
    prefix = 'Payload/Madeira.app/'
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'IPA CRC verification failed'
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate IPA paths'
        info = plistlib.loads(archive.read(prefix + 'Info.plist'))
        assert info['CFBundleIdentifier'] == lock['bundle_id']
        assert info['CFBundleDisplayName'] == lock['display_name']
        assert info['MyPCNativeSourceCommit'] == lock['source']['commit']
        assert info['MyPCNativeBackend'] == 'native-ios-fex-wine-metal'
        if 'GITHUB_SHA' in os.environ: assert info['SomethingPCBuildCommit'] == os.environ['GITHUB_SHA']
        binary = archive.read(prefix + info['CFBundleExecutable'])
        libraries = macho(binary, 2)
        debug_name = info['CFBundleExecutable'] + '.debug.dylib'
        # Xcode's unoptimized app layout uses a small MH_EXECUTE launcher and
        # stores the real app in a referenced MH_DYLIB. Verify both, preserving
        # the reference's device-tested Debug configuration.
        debug_layout = any(item.rsplit('/', 1)[-1] == debug_name for item in libraries)
        if debug_layout:
            binary = archive.read(prefix + debug_name)
            macho(binary, 6)
        assert len(binary) > 1_000_000, 'Host app code is unexpectedly small'
        prohibited = ('qemu', 'virgl', 'rootfs.raw', 'linuxruntime', 'libegl.framework', 'libglesv2.framework')
        assert not any(term in name.lower() for name in names for term in prohibited), 'VM payload included'
        for directory in ('arm64ec-windows', 'aarch64-windows', 'i386-windows', 'x86_64-vcruntime'):
            assert any(name.startswith(prefix + directory + '/') for name in names), directory
        for item in ('arm64ec-windows/dockhost.exe', 'arm64ec-windows/dock-notices.txt',
                     'licenses/LICENSE-MADEIRA-GPL-3.0.txt', 'licenses/LICENSE-MADEIRA-EXCEPTION.txt'):
            assert archive.getinfo(prefix + item).file_size > 0, item
        host = archive.read(prefix + 'arm64ec-windows/dockhost.exe')
        pe = struct.unpack_from('<I', host, 0x3c)[0]
        assert host[pe:pe + 4] == b'PE\0\0'
        assert struct.unpack_from('<H', host, pe + 4)[0] == 0x8664, 'Expected FEX-translated x64 Dock helper'
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    value = {'build': info['CFBundleVersion'], 'commit': info['SomethingPCBuildCommit'],
             'source': info['MyPCNativeSourceCommit'], 'bytes': path.stat().st_size,
             'sha256': digest, 'vm_payload': False, 'arm64_ios_host': True,
             'mach_o_platform': 'iOS', 'debug_dylib_layout': debug_layout}
    print(json.dumps(value, indent=2))
    return value


if __name__ == '__main__':
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
