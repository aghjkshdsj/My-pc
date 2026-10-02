#!/usr/bin/env python3
"""Inspect the exact compiled iOS engine; never count this as phone execution."""
import argparse
import hashlib
import json
import pathlib
import struct
import tarfile

from verify_ipa import macho_platform


def audit(directory):
    bundle = directory / 'MoltenVK-iOS-Framework.tar.gz'
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == '17665e978ab4746bfdfbb114e2deb6bface9b30f6a4b2e5656ef3271388c06c7'
    with tarfile.open(bundle) as archive:
        member = archive.getmember('Frameworks/MoltenVK.framework/MoltenVK')
        assert member.isfile() and member.size == 4837960
        binary = archive.extractfile(member).read()
    assert hashlib.sha256(binary).hexdigest() == '28276729e49021f50f1956a2eb51f5b95bec6a58b3ec59fe5f3206eda5dda41c'
    names = macho_platform(binary, 6)
    count = struct.unpack_from('<I', binary, 16)[0]
    cursor, imports = 32, []
    kinds = {0xc: 'required', 0x80000018: 'weak', 0x8000001f: 'reexport'}
    for _ in range(count):
        command, size = struct.unpack_from('<II', binary, cursor)
        if command in kinds:
            offset = struct.unpack_from('<I', binary, cursor + 8)[0]
            name = binary[cursor + offset:cursor + size].split(b'\0', 1)[0].decode()
            imports.append({'path': name, 'kind': kinds[command]})
        cursor += size
    assert [x['path'] for x in imports] == names
    result = {'scope': 'compiled-physical-ios-engine-load-command-audit',
              'build_run': 37036404372, 'engine_commit': '05604465d691118cfd20f53a48ecf1aad9c12f93',
              'physical_ios_arm64': True, 'imports': imports,
              'phone_loader_verified': False, 'vulkan_to_metal_execution_verified': False,
              'guest_transport_verified': False, 'gameplay_verified': False,
              'limitation': 'Load commands only. Weak imports still require guarded use; actual iOS loader and rendering tests remain required.'}
    (directory / 'load-command-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    audit(parser.parse_args().directory)
