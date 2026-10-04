#!/usr/bin/env python3
"""Check private owner reports against the exact verified guest-GPU IPA.

This is report consistency checking, not cryptographic device attestation or
independent host Metal/presentation evidence. Nothing is uploaded by this tool.
"""
import argparse
import hashlib
import json
import pathlib
import re
import zipfile

from run_kernel_gate import validate as validate_abi
from verify_device_report import measurement, require
from verify_ipa import verify as verify_ipa
from verify_guest_metal_trace import validate as validate_metal_trace


def validate(report, commit, build, payload, bundle, ios, machine=None, serial=None, image_import=False):
    test_key = "linux_image" if image_import else "linux_gpu"
    require(report.get('schema') == 1 and report.get('scope') == 'physical-ios-host-probe', 'Expected a phone report')
    require(report.get('source_commit') == commit and report.get('build') == build, 'Wrong IPA source/build')
    require(report.get('executed_tests') == [test_key], 'The guest GPU gate was not freshly executed')
    gate = report.get('tests', {}).get(test_key, {})
    require(gate.get('schema') == 1 and gate.get('scope') == ('physical-ios-linux-guest-image-gate' if image_import else 'physical-ios-linux-guest-vulkan-gate'), 'Wrong gate scope')
    require(gate.get('source_commit') == commit and gate.get('payload') == payload and gate.get('engine_bundle') == bundle,
            'Guest/engine provenance differs from the verified IPA')
    require(gate.get('engine_text_sections_verified') is True and
            gate.get('engine_text_sections_observed') == bundle.get('engine_text_sections'), 'Engine executable code differs')
    require(gate.get('status') == 'passed' and gate.get('linux_execution') is True and
            gate.get('engine_finished') is True and type(gate.get('engine_status')) is int and gate['engine_status'] == 0,
            'Linux engine/guest did not complete')
    require(gate.get('engine') == 'qemu-10.0.12-utm-aarch64-tcg' and
            gate.get('hardware_virtualization') is False and gate.get('steamos') is False, 'Wrong execution scope')
    require(gate.get('guest_gpu_device_requested') is True and gate.get('guest_gpu_host_visible_mib') == 128 and
            gate.get('requested_jit_cache_mib') == 32 and gate.get('split_wx_requested') is True, 'Wrong GPU/JIT configuration')
    if build in ('4000012', '4000013', '4000014', '4000015', '4000016', '4000017'):
        require(gate.get('display_backend_registered') is True, 'No observed built-in display backend registration')
    if build in ('4000014', '4000015', '4000016', '4000017'):
        require(gate.get('host_private_file_directory_prepared') is True,
                'No observed preparation of the app-private renderer namespace')
    device = gate.get('device', {})
    keys = ('device_machine', 'ios_version', 'os_build', 'host_page_bytes')
    require(str(device.get('device_machine', '')).startswith('iPhone') and device.get('ios_version') == ios,
            'Wrong phone/OS identity')
    require(machine is None or device.get('device_machine') == machine, 'Wrong phone model')
    require(device.get('os_build') not in (None, '', 'unknown', 'unavailable') and
            device.get('host_page_bytes') in (4096, 16384), 'Missing OS build/page facts')
    for facts in (report.get('before', {}), report.get('after', {}), gate.get('after', {})):
        require(all(facts.get(key) == device.get(key) for key in keys), 'Mixed device/OS identities')
    require(device.get('code_signing', {}).get('debugged') is True, 'Missing debug signing at boot')
    nonce = gate.get('run', '')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce), 'Invalid fresh boot nonce')
    text = gate.get('serial_tail', '') if serial is None else serial
    require(isinstance(text, str), 'Missing Linux serial')
    try:
        abi = validate_abi(text, nonce)
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid or truncated Linux ABI serial: ' + str(error)) from error
    require(abi == gate.get('guest') and str(abi.get('kernel', '')).startswith('6.12.111'), 'ABI serial disagrees')
    require(measurement(gate.get('elapsed_ms')) and all(measurement(abi.get(k)) for k in ('cpu_ms', 'wall_ms')),
            'Invalid timing; this timing is not game FPS')
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith('MPC_GPU_GUEST_RUN=')]
    exits = [i for i, line in enumerate(lines) if line.startswith('MPC_GPU_GUEST_EXIT=')]
    devices = [(i, line) for i, line in enumerate(lines) if line.startswith('MPC_GPU_KERNEL ')]
    draws = [(i, line) for i, line in enumerate(lines) if line.startswith('MPC_VK_DIAGNOSTIC ')]
    require(len(starts) == len(exits) == len(devices) == len(draws) == 1, 'Missing/duplicate GPU markers')
    require(lines[starts[0]] == 'MPC_GPU_GUEST_RUN=' + nonce and lines[exits[0]] == 'MPC_GPU_GUEST_EXIT=0' and
            starts[0] < devices[0][0] < draws[0][0] < exits[0], 'Stale, failed or unordered GPU run')
    try:
        gpu = json.loads(devices[0][1].removeprefix('MPC_GPU_KERNEL '))
        draw = json.loads(draws[0][1].removeprefix('MPC_VK_DIAGNOSTIC '))
    except (TypeError, ValueError) as error:
        raise ValueError('Malformed GPU serial receipt') from error
    require(isinstance(gpu, dict) and isinstance(draw, dict), 'Wrong GPU receipt kind')
    require(gpu == gate.get('graphics_kernel') and draw == gate.get('guest_vulkan'), 'GPU serial/parsed result differs')
    require(gpu.get('run') == nonce and gpu.get('driver') == 'virtio_gpu' and gpu.get('page_bytes') == 4096,
            'Wrong DRM driver/nonce/page size')
    parameters = gpu.get('parameters', {})
    require(isinstance(parameters, dict), 'Missing virtio-GPU capabilities')
    for key in ('1', '3', '4', '6'):
        parameter = parameters.get(key, {})
        require(isinstance(parameter, dict) and parameter.get('supported') is True and parameter.get('value') == 1,
                'Missing 3D/blob/host-visible/context capability: ' + key)
    expected = {'machine': 'aarch64', 'software': False, 'width': 1280, 'height': 720,
                'shader_phases': 2, 'pixels_checked': 1843200, 'mismatches': 0, 'channel_sum': 1219256320,
                'validation_errors': 0, 'metal_host_verified': False, 'presentation_verified': False,
                'game_fps_verified': False}
    require(all(type(draw.get(k)) is type(v) and draw[k] == v for k, v in expected.items()), 'Wrong pixels/device/scope')
    for key in ('fresh_guest_vulkan_nonce_bound', 'graphics_kernel_device_detected', 'guest_vulkan_pixels_verified', 'graphics_tested'):
        require(gate.get(key) is True, 'Parsed GPU acceptance disagrees: ' + key)
    native_metal = False
    if build in ('4000015', '4000016', '4000017'):
        require(gate.get('host_metal_completion_observer_requested') is True, 'Native guest observer was not requested')
        validate_metal_trace(gate.get('native_metal_trace'), nonce, device.get('metal_device'))
        require(gate.get('metal_host_verified') is True, 'Native completion and parsed result disagree')
        native_metal = True
    else:
        require(gate.get('metal_host_verified') is False, 'Guest pixels claim native completion without an observer')
    image_verified = False
    if image_import:
        from verify_guest_image_import import validate as validate_image
        validate_image(gate, text, nonce, device.get('metal_device'))
        require(gate.get('host_memory_import_verified') is True, 'Image acceptance disagrees')
        require(report.get('acceptance', {}).get('linux_guest_image_import') is True, 'Exported image acceptance disagrees')
        image_verified = True
    for key in (('presentation_verified', 'gameplay_verified') if image_import else ('host_memory_import_verified', 'presentation_verified', 'gameplay_verified')):
        require(gate.get(key) is False, 'Guest pixels claim independent host/game proof: ' + key)
    acceptance = report.get('acceptance', {})
    require(acceptance.get('linux_kernel_boot') is True and acceptance.get('linux_guest_vulkan_pixels') is True,
            'Exported acceptance disagrees')
    if build in ('4000015', '4000016', '4000017'):
        require(acceptance.get('linux_guest_offscreen_metal_completion') is True, 'Exported native completion disagrees')
    for key in ('steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal', 'steam_under_60_seconds',
                'hollow_knight_60_to_80_base_fps'):
        require(acceptance.get(key) is False, 'Unsupported product claim: ' + key)
    return {'schema': 1, 'scope': 'owner-supplied-iphone-guest-vulkan-evidence-consistency-check',
            'source_commit': commit, 'build': build, 'device': {k: device[k] for k in keys}, 'boot_nonce': nonce,
            'linux_kernel_abi_receipt_valid': True, 'guest_vulkan_pixels_receipt_valid': True,
            'execution': 'qemu-tcg-software-system-emulation', 'pixels_checked': draw['pixels_checked'],
            'gate_elapsed_ms': gate['elapsed_ms'], 'validation_layer_observed': draw.get('validation_enabled', False),
            'hardware_virtualization_verified': False, 'metal_host_verified': native_metal,
            'host_memory_import_verified': image_verified, 'presentation_verified': False, 'steamos_verified': False,
            'gameplay_verified': False, 'steam_startup_target_verified': False, 'hollow_knight_target_verified': False,
            'cryptographic_device_attestation': False}


def unpack_private(document, commit=None, build=None, image_import=False):
    test_key = "linux_image" if image_import else "linux_gpu"
    if document.get('scope') == 'physical-ios-host-probe':
        return document, None
    require(document.get('scope') == 'private-ios-interrupted-probe-diagnostics', 'Unknown private export scope')
    candidates = []
    for entry in document.get('files', []):
        if entry.get('tail_truncated') is not False:
            continue
        try:
            row = json.loads(entry.get('text', ''))
        except (TypeError, ValueError):
            continue
        if (isinstance(row, dict) and row.get('scope') == 'physical-ios-host-probe' and
                row.get('executed_tests') == [test_key] and
                row.get('tests', {}).get(test_key, {}).get('status') == 'passed' and
                (commit is None or row.get('source_commit') == commit) and
                (build is None or row.get('build') == build)):
            if row not in candidates:
                candidates.append(row)
    require(len(candidates) == 1, 'Need one complete freshly executed guest-GPU report; crash logs alone cannot pass')
    report = candidates[0]
    nonce = report.get('tests', {}).get(test_key, {}).get('run')
    serial = [e['text'] for e in document.get('files', []) if e.get('name') == 'serial.log' and
              e.get('relative_directory') == 'LinuxGate-' + str(nonce) and e.get('tail_truncated') is False]
    require(len(serial) == 1, 'Need complete serial logs for this exact guest nonce')
    return report, serial[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=pathlib.Path)
    parser.add_argument('ipa', type=pathlib.Path)
    parser.add_argument('commit')
    parser.add_argument('--ios-version', default='27.0.1')
    parser.add_argument('--machine', default='iPhone16,2')
    parser.add_argument('--image-import', action='store_true')
    args = parser.parse_args()
    require(__debug__, 'Do not run with python -O; package/ABI checks use assertions')
    package = verify_ipa(args.ipa, args.commit, True, None, True, True)
    with zipfile.ZipFile(args.ipa) as archive:
        prefix = 'Payload/MyPCSteamOSProbe.app/LinuxGuestGPU/'
        payload = json.loads(archive.read(prefix + 'payload-receipt.json'))
        bundle = json.loads(archive.read(prefix + 'engine-bundle.json'))
    report, serial = unpack_private(json.loads(args.report.read_text(encoding='utf-8-sig')), args.commit, package['build'], args.image_import)
    result = validate(report, args.commit, package['build'], payload, bundle, args.ios_version, args.machine, serial, args.image_import)
    result['report_sha256'] = hashlib.file_digest(args.report.open('rb'), 'sha256').hexdigest()
    result['verified_ipa_sha256'] = package['sha256']
    print(json.dumps(result, indent=2))
