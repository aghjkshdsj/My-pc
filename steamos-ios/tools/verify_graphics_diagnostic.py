#!/usr/bin/env python3
"""Verify hosted Vulkan correctness/rejection; never promote it to phone evidence."""
import argparse
import hashlib
import json
import pathlib


def validate(row, rejection_code, rejection_text):
    assert row['machine'] == 'aarch64', 'Expected hosted ARM64 Linux'
    assert (row['width'], row['height'], row['shader_phases'], row['pixels_checked']) == (1280, 720, 2, 1843200)
    assert row['mismatches'] == 0
    # Independently sum the integer pattern; no shader implementation is executed here.
    expected = 0
    for phase in (0, 41):
        expected += 720 * sum((x + phase) % 256 for x in range(1280))
        expected += 1280 * sum((y + phase) % 256 for y in range(720))
        expected += 1280 * 720 * ((165 ^ phase) + 255)
    assert row['channel_sum'] == expected
    assert row['software'] is True and row['device_type'] == 4
    assert row['validation_enabled'] is True and row['synchronization_validation_requested'] is True
    assert row['validation_errors'] == 0
    assert row['metal_host_verified'] is False
    assert row['presentation_verified'] is False and row['game_fps_verified'] is False
    assert len(row['device_extensions']) == len(set(row['device_extensions'])) > 0
    assert rejection_code == 20
    assert rejection_text.strip() == 'MPC_VK_REJECTED software_renderer=' + row['renderer']
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert len(args.source) == 40 and all(c in '0123456789abcdef' for c in args.source)
    lines = (args.directory / 'diagnostic.log').read_text().splitlines()
    matches = [line.removeprefix('MPC_VK_DIAGNOSTIC ') for line in lines if line.startswith('MPC_VK_DIAGNOSTIC ')]
    assert len(matches) == 1
    row = json.loads(matches[0])
    code = int((args.directory / 'rejection-exit-code.txt').read_text())
    expected = validate(row, code, (args.directory / 'rejection.log').read_text())
    receipt = {'scope': 'hosted-linux-arm64-software-diagnostic', 'source_commit': args.source,
               'workflow_run': args.run, 'diagnostic': row, 'expected_channel_sum': expected,
               'software_rejection_exit': code,
               'files': {name: {'bytes': (args.directory / name).stat().st_size,
                                'sha256': hashlib.sha256((args.directory / name).read_bytes()).hexdigest()}
                         for name in ['vk-gate', 'vertex.spv', 'fragment.spv', 'diagnostic.log',
                                      'validation.log', 'rejection.log', 'rejection-validation.log']},
               'phone_tested': False, 'guest_transport_verified': False,
               'metal_verified': False, 'steamos_verified': False, 'gameplay_verified': False}
    (args.directory / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('VULKAN_DIAGNOSTIC_OK: two real images; software correctly rejected; phone/Metal gates remain open')


if __name__ == '__main__':
    main()
