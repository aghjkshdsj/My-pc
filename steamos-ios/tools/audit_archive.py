#!/usr/bin/env python3
"""Read reference ZIP bytes without extracting or executing archive code."""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import zipfile

ROOT_FILES = {'.gitattributes', '.gitignore', 'README.md', 'CREDITS.md', 'LICENSE'}

def component(path):
    if path in ROOT_FILES:
        return 'root-metadata'
    if path == 'make-steamos-sm8550.sh':
        return 'image-assembly'
    if path.startswith('external-and-mods/'):
        return path.split('/')[1]
    return path.split('/')[0]

def audit(archive, output):
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    files = []
    urls = collections.defaultdict(set)
    counts = collections.Counter()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP names')
        for entry in z.infolist():
            p = pathlib.PurePosixPath(entry.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in entry.filename:
                raise ValueError('Unsafe ZIP path')
            if not p.parts or p.parts[0] != 'SteamOS-ARM-SM8550-main':
                raise ValueError('Unexpected ZIP root')
            if entry.is_dir():
                continue
            path = '/'.join(p.parts[1:])
            data = z.read(entry)  # Also checks each entry's CRC.
            group = component(path)
            counts[group] += 1
            row = {'path': path, 'component': group, 'bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest(), 'review': 'inventory-and-dependency-scan'}
            if data[:4] == b'\x7fELF':
                row['binary_format'] = 'ELF'
                row['elf_machine'] = int.from_bytes(data[18:20], 'little' if data[5] == 1 else 'big')
            try:
                value = data.decode('utf-8')
                if '\x00' not in value:
                    row['text'] = True
                    row['license_file'] = bool(re.search(r'(?i)(^|/)(copying|licen[cs]e|copyright|notice)', path))
                    for url in re.findall(r'https?://[^\s\x00<>"\x27`]+', value):
                        urls[url.rstrip(').,;]')].add(path)
                    row['audit_flags'] = [name for name, pattern in {
                        'tls-verification-bypass': r'curl\s+[^\n]*\s-k\b|verify\s*=\s*False',
                        'partition-management': r'\b(sgdisk|parted|mkfs|wipefs|dd\s+if=)\b',
                        'unpinned-clone': r'git clone',
                        'bootstrap-check-bypass': r'noverifyfiles|nobootstrapupdate|skipinitialbootstrap|nocheckfiles',
                        'linux-hardware-interface': r'/sys/|/dev/dri|/dev/kgsl|/dev/input|/dev/uinput',
                    }.items() if re.search(pattern, value)]
            except UnicodeDecodeError:
                pass
            files.append(row)
    result = {'schema': 1, 'archive_name': archive.name, 'sha256': digest,
              'compressed_bytes': archive.stat().st_size, 'entries': len(names),
              'files': len(files), 'expanded_bytes': sum(x['bytes'] for x in files),
              'zip_crc': 'passed-all-files', 'component_counts': dict(sorted(counts.items())),
              'files_detail': files,
              'external_references': [{'url': url, 'files': sorted(paths)} for url, paths in sorted(urls.items())],
              'limitations': 'Every file was hashed and scanned. This is not a line-by-line semantic audit of every vendored implementation.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('files_detail', 'external_references')}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    audit(args.archive, args.output)
