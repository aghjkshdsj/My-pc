#!/usr/bin/env python3
"""Inspect official Valve ARM RAUC metadata only; never mount/boot its image."""
import configparser
import hashlib
import json
import pathlib
import struct
import subprocess
import urllib.request

BASE = 'https://steamdeck-images.steamos.cloud/vr/20260921.6090922/deckard-20260921.6090922-0.5.0.'
EXPECTED = {'manifest.json': '57b0943f0116c2163ddd355a50ec9c41dca254598dbf33a351b300067d15c595',
            'raucb': '8d413afc087069418540f05a2f78a72bfc74771023c1f3dc08b47277b5717f15'}

def inspect(output):
    output.mkdir(parents=True, exist_ok=False)
    receipts = {}
    for name, expected in EXPECTED.items():
        with urllib.request.urlopen(BASE + name, timeout=60) as response: data = response.read()
        assert hashlib.sha256(data).hexdigest() == expected, name
        (output / name).write_bytes(data)
        receipts[name] = {'sha256': expected, 'bytes': len(data), 'url': BASE + name}
    external = json.loads((output / 'manifest.json').read_text())
    assert external['product'] == 'steamos' and external['arch'] == 'aarch64'
    listing = subprocess.check_output(['unsquashfs', '-ll', str(output / 'raucb')], text=True)
    (output / 'bundle-listing.txt').write_text(listing)
    subprocess.run(['unsquashfs', '-no-progress', '-d', str(output / 'unpacked'), str(output / 'raucb')], check=True)
    manifests = list((output / 'unpacked').rglob('manifest.raucm'))
    assert len(manifests) == 1
    config = configparser.ConfigParser(interpolation=None)
    config.read(manifests[0])
    indexes = []
    for path in sorted((output / 'unpacked').rglob('*.caibx')):
        data = path.read_bytes()
        assert len(data) >= 104 and (len(data) - 64) % 40 == 0
        header, magic, flags, minimum, average, maximum = struct.unpack_from('<6Q', data)
        assert header == 48 and magic == 0x96824D9C7B129FF9
        table_size, table_magic = struct.unpack_from('<2Q', data, 48)
        assert table_magic == 0xE75B9E112F17417D
        body = data[64:]
        assert struct.unpack_from('<Q', body, len(body) - 8)[0] == 0x4B4F050E5549ECD1
        previous = 0
        for offset in range(0, len(body) - 40, 40):
            end = struct.unpack_from('<Q', body, offset)[0]
            assert 0 < end - previous <= maximum
            previous = end
        indexes.append({'filename': path.relative_to(output / 'unpacked').as_posix(),
            'sha256': hashlib.sha256(data).hexdigest(), 'index_bytes': len(data),
            'image_bytes': previous, 'chunks': (len(body) // 40) - 1,
            'feature_flags': flags, 'min_chunk': minimum, 'avg_chunk': average, 'max_chunk': maximum})
    assert indexes
    result = {'schema': 1, 'scope': 'official-steamos-arm-metadata-inspection',
        'manifest': external, 'downloads': receipts,
        'rauc_manifest': {section: dict(config[section]) for section in config.sections()},
        'indexes': indexes, 'store_url': BASE[:-1] + '.castr/',
        'signature_authenticated': False, 'rootfs_reconstructed': False,
        'linux_boot_verified': False, 'phone_tested': False,
        'limitation': 'Pinned HTTPS bundle bytes and internal format were checked. RAUC CMS certificate authentication and full image/chunk verification remain required. Metadata listing is not OS execution.'}
    (output / 'rootfs-metadata.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=pathlib.Path)
    inspect(parser.parse_args().output)
