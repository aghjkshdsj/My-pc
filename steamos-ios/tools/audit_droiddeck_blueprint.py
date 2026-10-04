#!/usr/bin/env python3
"""Inventory the owner-supplied Android blueprint without executing its code."""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import stat
import zipfile


def group(name):
    if name.startswith('keystore/') or name.endswith(('.jks', '.keystore', '.p12', '.pfx', '.pem')):
        return 'signing-material-withheld'
    for prefix, category in [
        ('app/src/main/cpp/adrenotools/', 'adreno-driver-loader'),
        ('app/src/main/cpp/thirdparty/', 'vendored-shader-translator'),
        ('app/src/main/cpp/framegen/', 'frame-generation'),
        ('app/src/main/cpp/waylandcomp/', 'android-wayland-compositor'),
        ('app/src/main/cpp/', 'other-native-host'),
        ('app/src/main/jniLibs/', 'android-prebuilt-libraries'),
        ('app/src/main/assets/', 'runtime-driver-audio-assets'),
        ('app/src/main/java/com/droiddeck/launcher/', 'android-application'),
        ('app/src/main/res/', 'ui-resources-localization'),
        ('app/src/test/', 'android-tests'),
        ('app/src/debug/', 'debug-control'),
        ('tools/linuxfs/', 'linux-session-desktop-shims'),
        ('tools/proot/', 'linux-process-path-translation'),
        ('tools/droiddeck-esync/', 'proton-synchronization-packs'),
        ('tools/aaudio-sink/', 'android-audio-adapters'),
        ('tools/gamescope/', 'external-gamescope-build'),
        ('tools/wlroots/', 'external-wlroots-build'),
        ('tools/mangoapp/', 'external-performance-overlay'),
        ('tools/tests/', 'linux-script-tests'),
        ('tools/release/', 'android-release-updates'),
        ('tools/', 'other-build-control-tools'),
        ('.github/', 'android-build-workflows'),
        ('docs/', 'reference-documents-media'),
        ('artwork/', 'reference-artwork'),
        ('gradle/', 'android-build-wrapper'),
    ]:
        if name.startswith(prefix):
            return category
    return 'root-build-metadata'


def audit(archive, output):
    output.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    sizes = collections.Counter()
    rows = []
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        for member in entries:
            path = pathlib.PurePosixPath(member.filename)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[0] == 'DroidDeck-main' and '\\' not in member.filename
            assert member.filename not in seen, 'Duplicate archive name'
            seen.add(member.filename)
            assert not stat.S_ISLNK(member.external_attr >> 16)
            if member.is_dir():
                continue
            total += member.file_size
            assert total < 512 * 1024 * 1024 and member.file_size < 128 * 1024 * 1024
            data = z.read(member)  # zipfile verifies this entry's CRC here.
            relative = pathlib.PurePosixPath(*path.parts[1:]).as_posix()
            category = group(relative)
            counts[category] += 1
            sizes[category] += len(data)
            withheld = category == 'signing-material-withheld'
            # Account for signing inputs without exporting a key, key path or key digest.
            public_name = f'withheld-signing-input-{counts[category]}' if withheld else relative
            rows.append({'path': public_name, 'group': category, 'bytes': len(data),
                         'sha256': 'withheld' if withheld else hashlib.sha256(data).hexdigest()})
    with (output / 'droiddeck-files.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['path', 'group', 'bytes', 'sha256'])
        writer.writeheader()
        writer.writerows(rows)
    summary = {'schema': 1, 'scope': 'android-blueprint-archive-inventory-only',
               'archive': archive.name, 'bytes': archive.stat().st_size,
               'sha256': hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest(),
               'entries': len(entries), 'files': len(rows), 'expanded_bytes': total,
               'all_file_crc_passed': True,
               'groups': {k: {'files': counts[k], 'bytes': sizes[k]} for k in sorted(counts)},
               'source_commit_established': False, 'scripts_executed': False,
               'source_application_reused': False, 'signing_content_exported': False,
               'complete_line_by_line_semantic_review': False,
               'phone_linux_gpu_verified': False, 'steam_boot_verified': False,
               'game_performance_verified': False}
    (output / 'droiddeck-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive, args.output), indent=2))
