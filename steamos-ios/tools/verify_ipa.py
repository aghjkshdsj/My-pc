#!/usr/bin/env python3
"""Verify exact identity and ARM64 iOS Mach-O; explicitly mark probe scope."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import struct
import zipfile

def verify(path, commit):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, 'IPA ZIP CRC failed'
        prefix = 'Payload/MyPCSteamOSProbe.app/'
        info = plistlib.loads(z.read(prefix + 'Info.plist'))
        assert info['CFBundleIdentifier'] == 'com.aghjkshdsj.mypc.steamos.probe'
        assert info['MPCSourceCommit'] == commit
        binary = z.read(prefix + info['CFBundleExecutable'])
        magic, cpu, subtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<8I', binary)
        assert magic == 0xfeedfacf and cpu == 0x100000c and filetype == 2, 'Expected ARM64 Mach-O executable'
        assert 32 + sizeofcmds <= len(binary) and ncmds <= 1024
        offset, ios = 32, False
        for _ in range(ncmds):
            command, size = struct.unpack_from('<II', binary, offset)
            assert size >= 8 and offset + size <= 32 + sizeofcmds
            if command == 0x32:
                ios = struct.unpack_from('<I', binary, offset + 8)[0] == 2
            offset += size
        assert ios, 'Mach-O must target physical iOS'
        assert not any('Madeira' in p or 'NativeSteam' in p for p in z.namelist()), 'Old app contamination'
        return {'schema': 1, 'kind': 'ios-host-probe-only', 'commit': commit, 'build': info['CFBundleVersion'],
                'bundle_id': info['CFBundleIdentifier'], 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(),
                'bytes': path.stat().st_size, 'zip_crc': 'passed', 'arm64_ios': True,
                'linux_boot_verified': False, 'game_graphics_verified': False, 'phone_performance_verified': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ipa', type=pathlib.Path)
    parser.add_argument('commit')
    parser.add_argument('--receipt', type=pathlib.Path)
    args = parser.parse_args()
    result = verify(args.ipa, args.commit)
    text = json.dumps(result, indent=2) + '\n'
    if args.receipt:
        args.receipt.write_text(text, encoding='utf-8')
    print(text)
