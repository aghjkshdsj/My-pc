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
        assert binary[:4] == b'\xcf\xfa\xed\xfe', 'Expected little-endian 64-bit Mach-O'
        assert struct.unpack_from('<I', binary, 4)[0] == 0x0100000c, 'Expected ARM64 host'
        assert len(binary) > 1_000_000, 'Host executable is unexpectedly small'
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
             'sha256': digest, 'vm_payload': False, 'arm64_ios_host': True}
    print(json.dumps(value, indent=2))
    return value


if __name__ == '__main__':
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
