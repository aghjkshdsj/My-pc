#!/usr/bin/env python3
"""Bounded read-only requests to primary endpoints. No remote code execution."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import urllib.error
import urllib.request

SOURCES = {
    'apple-hypervisor': 'https://developer.apple.com/tutorials/data/documentation/hypervisor.json',
    'apple-virtualization': 'https://developer.apple.com/tutorials/data/documentation/virtualization.json',
    'steam-arm-stable': 'https://client-update.steamstatic.com/steam_client_steamdeck_stable_linuxarm64',
    'steam-arm-beta': 'https://client-update.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64',
    'utm-build': 'https://raw.githubusercontent.com/utmapp/UTM/main/scripts/build_dependencies.sh',
    'utm-versions': 'https://raw.githubusercontent.com/utmapp/UTM/main/scripts/versions.sh',
    'kosmickrisp': 'https://docs.mesa3d.org/drivers/kosmickrisp.html',
    'venus': 'https://docs.mesa3d.org/drivers/venus.html',
}

def fetch(item):
    name, url = item
    row = {'id': name, 'url': url, 'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'MyPCSteamOS-research/1'}), timeout=30) as response:
            data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError('Response exceeds research bound')
            row.update(http_status=response.status, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       content_type=response.headers.get('Content-Type'), last_modified=response.headers.get('Last-Modified'))
        text = data.decode('utf-8')
        if name.startswith('apple-'):
            document = json.loads(text)
            row['platforms'] = document.get('metadata', {}).get('platforms', [])
            row['title'] = document.get('metadata', {}).get('title')
        elif name.startswith('steam-'):
            row['contains_arm_package'] = 'bins_linuxarm64_linuxarm64.zip' in text
            # Public manifests contain package metadata, not account data.
            (OUTPUT / (name + '.vdf')).write_bytes(data)
        elif name.startswith('utm-'):
            (OUTPUT / (name + '.txt')).write_bytes(data)
    except Exception as error:
        row['error'] = str(error)
    return row

if __name__ == '__main__':
    OUTPUT = pathlib.Path(__file__).resolve().parents[1] / 'evidence' / 'primary'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, SOURCES.items()))
    (OUTPUT / 'receipts.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(rows, indent=2))
