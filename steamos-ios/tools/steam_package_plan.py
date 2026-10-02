#!/usr/bin/env python3
"""Resolve all packages in the official ARM manifest; never install or execute."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import re
import urllib.request

def parse(text):
    assert len(text) <= 1024 * 1024
    decoder = json.JSONDecoder()
    tokens, position = [], 0
    while position < len(text):
        if text[position].isspace(): position += 1; continue
        if text.startswith('//', position):
            end = text.find('\n', position)
            position = len(text) if end < 0 else end + 1
            continue
        if text[position] in '{}': tokens.append(text[position]); position += 1; continue
        assert text[position] == '"', 'Unexpected VDF token'
        value, count = decoder.raw_decode(text[position:])
        assert isinstance(value, str)
        tokens.append(('string', value)); position += count
    cursor = 0
    def block(depth):
        nonlocal cursor
        assert depth < 8
        result = {}
        while cursor < len(tokens) and tokens[cursor] != '}':
            key = tokens[cursor]; cursor += 1
            assert isinstance(key, tuple) and key[0] == 'string'
            assert key[1] not in result, 'Duplicate manifest key'
            value = tokens[cursor]; cursor += 1
            if value == '{':
                result[key[1]] = block(depth + 1)
                assert cursor < len(tokens) and tokens[cursor] == '}'
                cursor += 1
            else:
                assert isinstance(value, tuple) and value[0] == 'string'
                result[key[1]] = value[1]
        return result
    result = block(0)
    assert cursor == len(tokens), 'Unbalanced manifest'
    return result

def plan(path):
    data = path.read_bytes()
    tree = parse(data.decode())
    assert 'linuxarm64' in tree and set(tree) <= {'linuxarm64', 'kvsign2', 'kvsignatures'}, 'Wrong client architecture'
    root = tree['linuxarm64']
    assert re.fullmatch(r'[0-9]+', root['version'])
    packages = []
    for name, value in root.items():
        if name == 'version': continue
        assert isinstance(value, dict) and re.fullmatch(r'[A-Za-z0-9_.-]+', value['file'])
        assert re.fullmatch(r'[a-f0-9]{64}', value['sha2'])
        size = int(value['size']); assert 0 < size <= 8 * 1024**3
        packages.append({'name': name, 'file': value['file'], 'bytes': size,
            'sha256': value['sha2'], 'url': 'https://client-update.steamstatic.com/' + value['file'],
            'alternative_vzip_present': 'zipvz' in value, 'download_verified': False})
    assert any(x['name'] == 'bins_linuxarm64' for x in packages)
    return {'schema': 1, 'platform': 'linuxarm64', 'version': root['version'],
        'manifest_sha256': hashlib.sha256(data).hexdigest(), 'package_count': len(packages),
        'zip_download_bytes': sum(x['bytes'] for x in packages), 'packages': packages,
        'scope': 'complete-client-manifest-plan', 'installed': False, 'linux_or_phone_executed': False,
        'manifest_signature_sections': {key: tree[key] for key in ['kvsign2', 'kvsignatures'] if key in tree},
        'valve_signature_verified': False,
        'limitation': 'No package binary is installed or redistributed by this tool; HEAD is availability, not digest verification. Plain ZIP chosen; Valve VZip decoding is not implemented.'}

def head(row):
    result = dict(row)
    try:
        with urllib.request.urlopen(urllib.request.Request(row['url'], method='HEAD'), timeout=30) as response:
            length = response.headers.get('Content-Length')
            result['head'] = {'status': response.status, 'bytes': int(length) if length else None,
                'final_url': response.geturl(), 'length_matches': length is not None and int(length) == row['bytes']}
    except Exception as error:
        result['head'] = {'error': str(error)}
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    parser.add_argument('--check-head', action='store_true')
    args = parser.parse_args()
    result = plan(args.manifest)
    if args.check_head:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result['packages'] = list(pool.map(head, result['packages']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'packages'}, indent=2))
    if args.check_head:
        print(json.dumps([x for x in result['packages'] if not x['head'].get('length_matches')], indent=2))
