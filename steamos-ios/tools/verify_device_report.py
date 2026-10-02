#!/usr/bin/env python3
"""Check owner-supplied phone evidence against an independently verified IPA.

This checks report consistency, not cryptographic device attestation. Reports
remain private; this tool does not upload them or mark Steam/game gates passed.
"""
import argparse
import hashlib
import json
import math
import pathlib
import re
import statistics
import zipfile

from run_kernel_gate import validate as validate_guest
from verify_ipa import verify as verify_ipa


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def measurement(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_jit(report, expected_commit, expected_build, ios_version, machine=None):
    require(report.get('schema') == 1 and report.get('scope') == 'physical-ios-host-probe', 'Expected physical iOS host probe')
    require(report.get('source_commit') == expected_commit and report.get('build') == expected_build,
            'JIT report source/build differs from the verified IPA')
    before, after = report.get('before', {}), report.get('after', {})
    keys = ('device_machine', 'ios_version', 'os_build', 'host_page_bytes')
    require(all(before.get(k) == after.get(k) for k in keys), 'Mixed JIT device/OS identities')
    require(str(before.get('device_machine', '')).startswith('iPhone'), 'Expected an iPhone')
    require(before.get('ios_version') == ios_version and before.get('os_build') not in (None, '', 'unknown', 'unavailable'),
            'Missing or unexpected iOS identity')
    require(machine is None or before.get('device_machine') == machine, 'Unexpected iPhone machine')
    require(before.get('host_page_bytes') in (4096, 16384), 'Unexpected host page size')
    jit = report.get('tests', {}).get('jit', {})
    require(jit.get('status') == 'passed' and type(jit.get('returned')) is int and jit['returned'] == 42,
            'No successful execution of the fixed ARM64 stub')
    require(jit.get('execution') == 'native-arm64-local-jit-stub' and jit.get('linux_execution') is False,
            'JIT execution scope is inconsistent')
    require(jit.get('protocol') == 'stikdebug-universal-prepared-rx-writable-alias', 'Unexpected JIT preparation protocol')
    require(before.get('code_signing', {}).get('debugged') is True and
            before.get('code_signing', {}).get('get_task_allow') is True, 'No observed debug signing entitlement')
    if jit.get('rx_region_reused') is not True:
        require(before.get('code_signing', {}).get('debugger_attached') is True, 'No debugger for fresh RX preparation')
    for key in ('linux_kernel_boot', 'steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal',
                'steam_under_60_seconds', 'hollow_knight_60_to_80_base_fps'):
        require(report.get('acceptance', {}).get(key) is False, 'JIT-only receipt claims another gate: ' + key)
    return {'scope': 'owner-supplied-iphone-jit-evidence-consistency-check', 'source_commit': expected_commit,
            'build': expected_build, 'device': {k: before[k] for k in keys},
            'native_arm64_jit_execution_verified': True, 'returned': 42,
            'rx_region_reused': jit.get('rx_region_reused', False), 'linux_boot_verified': False,
            'steamos_verified': False, 'guest_graphics_to_metal_verified': False,
            'steam_startup_target_verified': False, 'hollow_knight_target_verified': False,
            'cryptographic_device_attestation': False}


def validate_native_vulkan(report, expected_commit, expected_build, payload, ios_version, machine=None):
    require(report.get('scope') == 'physical-ios-host-probe' and report.get('schema') == 1, 'Expected a physical iOS report')
    require(report.get('source_commit') == expected_commit and report.get('build') == expected_build, 'Graphics source/build differs from IPA')
    before, after = report.get('before', {}), report.get('after', {})
    keys = ('device_machine', 'ios_version', 'os_build', 'host_page_bytes')
    require(all(before.get(k) == after.get(k) for k in keys), 'Mixed graphics device/OS identity')
    require(str(before.get('device_machine', '')).startswith('iPhone') and before.get('ios_version') == ios_version,
            'Unexpected graphics phone identity')
    require(machine is None or before.get('device_machine') == machine, 'Unexpected graphics machine')
    require(before.get('os_build') not in (None, '', 'unknown') and before.get('host_page_bytes') in (4096, 16384), 'Missing graphics OS/page evidence')
    gate = report.get('tests', {}).get('native_vulkan', {})
    require(gate.get('scope') == 'physical-ios-native-vulkan-offscreen-gate' and gate.get('status') == 'passed' and
            gate.get('exit_status') == 0 and gate.get('native_vulkan_to_metal_verified') is True, 'Native Vulkan draw did not pass')
    require(gate.get('payload') == payload and gate.get('path') == 'native-ios-arm64-vulkan-MoltenVK-Metal-offscreen', 'Wrong graphics engine or shaders')
    require(gate.get('linux_graphics') is False and gate.get('presentation_verified') is False and gate.get('gameplay_verified') is False,
            'Native offscreen evidence claims guest/presentation/game completion')
    draw = gate.get('diagnostic', {})
    expected = {'machine': before['device_machine'], 'software': False, 'vendor_id': 0x106b, 'device_type': 1,
                'width': 1280, 'height': 720, 'shader_phases': 2, 'pixels_checked': 1843200,
                'mismatches': 0, 'channel_sum': 1219256320, 'validation_errors': 0}
    require(all(draw.get(k) == v for k, v in expected.items()), 'Wrong graphics identity, pixels or checksum')
    require(measurement(gate.get('elapsed_ms')), 'Invalid graphics elapsed time')
    require(report.get('acceptance', {}).get('native_vulkan_to_metal_offscreen') is True, 'Graphics acceptance disagrees')
    for key in ('steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal', 'steam_under_60_seconds', 'hollow_knight_60_to_80_base_fps'):
        require(report.get('acceptance', {}).get(key) is False, 'Native offscreen receipt claims product gate: ' + key)
    return {'scope': 'owner-supplied-iphone-native-vulkan-evidence-consistency-check', 'source_commit': expected_commit,
            'build': expected_build, 'device': {k: before[k] for k in keys},
            'native_vulkan_to_metal_offscreen_verified': True, 'pixels_checked': draw['pixels_checked'],
            'elapsed_ms': gate['elapsed_ms'], 'validation_layer_observed': draw.get('validation_enabled', False),
            'linux_graphics_to_metal_verified': False, 'presentation_verified': False, 'gameplay_verified': False,
            'cryptographic_device_attestation': False}


def validate(report, expected_commit, expected_build, payload, ios_version, machine=None):
    require(report.get('schema') == 1 and report.get('scope') == 'physical-ios-host-probe',
            'Expected an exported physical iOS probe report, not hosted evidence')
    require(report.get('source_commit') == expected_commit and report.get('build') == expected_build,
            'Report source/build differs from the verified IPA')
    tests = report.get('tests', {})
    linux = tests.get('linux', {})
    require(linux.get('schema') == 1 and linux.get('scope') == 'physical-ios-linux-tcg-gate',
            'Missing physical Linux gate receipt')
    require(linux.get('source_commit') == expected_commit and linux.get('payload') == payload,
            'Linux source/payload differs from the verified IPA')
    require(linux.get('status') == 'passed' and linux.get('linux_execution') is True and
            linux.get('engine_finished') is True and type(linux.get('engine_status')) is int and
            linux['engine_status'] == 0, 'Linux engine did not complete successfully')
    require(linux.get('engine') == 'qemu-10.0.12-utm-aarch64-tcg' and
            linux.get('hardware_virtualization') is False and linux.get('steamos') is False and
            linux.get('graphics_tested') is False, 'CPU gate scope/engine is inconsistent')
    device = linux.get('device', {})
    identity_keys = ('device_machine', 'ios_version', 'os_build', 'host_page_bytes')
    require(str(device.get('device_machine', '')).startswith('iPhone'), 'Expected an iPhone device')
    require(device.get('ios_version') == ios_version, 'iOS version differs from the expected phone')
    if machine:
        require(device.get('device_machine') == machine, 'Device machine differs from the expected phone')
    require(device.get('os_build') not in (None, '', 'unknown', 'unavailable'), 'Missing actual OS build')
    require(device.get('host_page_bytes') in (4096, 16384), 'Invalid recorded host page size')
    for facts in (report.get('before', {}), report.get('after', {}), linux.get('after', {})):
        require(all(facts.get(key) == device.get(key) for key in identity_keys), 'Mixed device/OS identities')
    require(device.get('code_signing', {}).get('debugged') is True, 'No debugged signing state at boot')
    nonce = linux.get('run', '')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce), 'Missing fresh-format boot nonce')
    try:
        guest = validate_guest(linux.get('serial_tail', ''), nonce)
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid guest serial receipt: ' + str(error)) from error
    require(guest == linux.get('guest'), 'Serial receipt and parsed guest disagree')
    require(str(guest.get('kernel', '')).startswith('6.12.111'), 'Unexpected bundled guest kernel')
    require(all(measurement(guest.get(key)) for key in ('wall_ms', 'cpu_ms')) and
            measurement(linux.get('elapsed_ms')), 'Invalid Linux timing measurements')
    acceptance = report.get('acceptance', {})
    require(acceptance.get('linux_kernel_boot') is True, 'Exported Linux acceptance disagrees')
    for key in ('steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal',
                'steam_under_60_seconds', 'hollow_knight_60_to_80_base_fps'):
        require(acceptance.get(key) is False, 'CPU-only report claims an unsupported gate: ' + key)
    result = {'schema': 1, 'scope': 'owner-supplied-iphone-linux-evidence-consistency-check',
              'source_commit': expected_commit, 'build': expected_build,
              'device': {key: device[key] for key in identity_keys}, 'boot_nonce': nonce,
              'linux_kernel_abi_receipt_valid': True, 'execution': 'qemu-tcg-software-system-emulation',
              'boot_and_abi_elapsed_ms': linux['elapsed_ms'], 'guest_cpu_ms': guest['cpu_ms'],
              'guest_wall_ms': guest['wall_ms'], 'hardware_virtualization_verified': False,
              'steamos_verified': False, 'guest_graphics_to_metal_verified': False,
              'steam_startup_target_verified': False, 'hollow_knight_target_verified': False,
              'cryptographic_device_attestation': False}
    native = tests.get('native_cpu', {})
    trials = native.get('trials', [])
    if native.get('status') == 'passed':
        require(native.get('execution') == 'native-ios-arm64' and
                native.get('iterations_per_trial') == 1000000 and len(trials) == 5,
                'Invalid native comparison workload')
        require(all(t.get('checksum') == '1d250c45a7bbc87e' and
                    measurement(t.get('wall_ms')) for t in trials), 'Invalid native CPU measurements')
        median = statistics.median(t['wall_ms'] for t in trials)
        result['native_cpu_median_wall_ms'] = median
        result['guest_over_native_wall_ratio'] = guest['wall_ms'] / median if median > 0 else None
        result['comparison_limit'] = 'Single guest run versus native median; scheduling/cache/thermal effects. Not game FPS.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=pathlib.Path)
    parser.add_argument('ipa', type=pathlib.Path)
    parser.add_argument('commit')
    parser.add_argument('--ios-version', default='27.0.1')
    parser.add_argument('--machine')
    parser.add_argument('--gate', choices=['jit', 'linux', 'native-vulkan'], default='linux')
    args = parser.parse_args()
    require(__debug__, 'Run this verifier without python -O; IPA/guest checks use assertions')
    package = verify_ipa(args.ipa, args.commit, linux_gate=True, native_vulkan=args.gate == 'native-vulkan')
    with zipfile.ZipFile(args.ipa) as archive:
        payload = json.loads(archive.read('Payload/MyPCSteamOSProbe.app/LinuxGate/payload-receipt.json'))
        native_payload = json.loads(archive.read('Payload/MyPCSteamOSProbe.app/NativeVulkan/payload-receipt.json')) if args.gate == 'native-vulkan' else None
    report = json.loads(args.report.read_text(encoding='utf-8-sig'))
    if args.gate == 'jit': result = validate_jit(report, args.commit, package['build'], args.ios_version, args.machine)
    elif args.gate == 'native-vulkan': result = validate_native_vulkan(report, args.commit, package['build'], native_payload, args.ios_version, args.machine)
    else: result = validate(report, args.commit, package['build'], payload, args.ios_version, args.machine)
    result['report_sha256'] = hashlib.file_digest(args.report.open('rb'), 'sha256').hexdigest()
    result['verified_ipa_sha256'] = package['sha256']
    print(json.dumps(result, indent=2))
