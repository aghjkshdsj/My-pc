#!/usr/bin/env python3
"""Real ARM kernel/device test and missing-device rejection, never Metal proof."""
import argparse
import hashlib
import json
import math
import os
import pathlib
import subprocess
import uuid

from run_kernel_gate import validate as validate_abi


def validate(text, nonce, device_present):
    abi = validate_abi(text, nonce)
    lines = [x.removeprefix('MPC_GPU_KERNEL ') for x in text.splitlines() if x.startswith('MPC_GPU_KERNEL ')]
    assert len(lines) == 1, 'Missing/duplicate kernel GPU receipt'
    row = json.loads(lines[0])
    assert row['schema'] == 1 and row['scope'] == 'linux-virtio-gpu-kernel-device'
    assert row['run'] == nonce and len(nonce) == 32
    assert row['machine'] == 'aarch64' and row['page_bytes'] == 4096
    assert row['kernel'].startswith('6.12.111')
    assert isinstance(row['wall_ms'], (float, int)) and math.isfinite(row['wall_ms']) and row['wall_ms'] >= 0
    for name in ['gpu_shader_verified', 'host_pixels_verified', 'metal_verified', 'presentation_verified', 'gameplay_verified']:
        assert row[name] is False, 'Kernel memory/device evidence cannot claim accelerated graphics'
    if device_present:
        assert row['driver'] == 'virtio_gpu' and row['stage'] == 'complete'
        assert row['exit_code'] == row['errno'] == row['mismatches'] == 0
        assert row['width'] == 1280 and row['height'] == 720
        assert row['mapped_bytes'] == 3686400 and row['mapped_sum'] == 470016000
        assert all(row[name] is True for name in ['mapped_resource_verified', 'transfer_ioctl_completed', 'resource_closed'])
        assert row['parameters']['2'] == {'supported': True, 'value': 1}
        # This specifically tests the QEMU 2D path; do not mistake it for Venus.
        assert row['parameters']['1'] == {'supported': True, 'value': 0}
        assert row['parameters']['3']['value'] == row['parameters']['4']['value'] == row['parameters']['6']['value'] == 0
        assert 'MPC_GPU_KERNEL_EXIT=0' in text
    else:
        assert row['stage'] == 'open-drm' and row['driver'] == ''
        assert row['exit_code'] == 1 and row['errno'] == 2
        assert all(row[name] is False for name in ['mapped_resource_verified', 'transfer_ioctl_completed', 'resource_closed'])
        assert 'MPC_GPU_KERNEL_EXIT=1' in text
    return {'abi': abi, 'kernel_gpu': row}


def run(payload, device_present):
    nonce = uuid.uuid4().hex
    command = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max',
               '-accel', 'tcg,thread=multi,split-wx=on,tb-size=32', '-smp', '2', '-m', '512',
               '-nodefaults', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
               '-kernel', str(payload / 'Image'), '-initrd', str(payload / 'initramfs.cpio.gz'),
               '-append', 'console=ttyAMA0 rdinit=/init panic=1 mpc_run=' + nonce, '-no-reboot']
    if device_present:
        command += ['-device', 'virtio-gpu-pci']
    case = 'device' if device_present else 'missing-device'
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    except subprocess.TimeoutExpired as error:
        (payload / (case + '.log')).write_bytes(error.stdout or b'')
        raise
    (payload / (case + '.log')).write_bytes(process.stdout)
    text = process.stdout.decode('utf-8', errors='strict')
    print(text)
    assert process.returncode == 0, 'Engine did not shut down successfully'
    row = validate(text, nonce, device_present)
    return {'command': command, 'engine_exit': process.returncode,
            'serial_sha256': hashlib.sha256(process.stdout).hexdigest(), **row}


def main(payload):
    metadata = json.loads((payload / 'payload-receipt.json').read_text(encoding='utf-8'))
    assert metadata['kind'] == 'disposable-linux-virtio-gpu-kernel-gate'
    for name, receipt in metadata['files'].items():
        assert pathlib.PurePosixPath(name).name == name
        data = (payload / name).read_bytes()
        assert len(data) == receipt['bytes'] and hashlib.sha256(data).hexdigest() == receipt['sha256']
    device = run(payload, True)
    rejected = run(payload, False)
    assert device['kernel_gpu']['run'] != rejected['kernel_gpu']['run']
    receipt = {'schema': 1, 'scope': 'hosted-arm-linux-virtio-gpu-kernel-device-test',
               'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
               'engine_version': subprocess.check_output(['qemu-system-aarch64', '--version'], text=True).splitlines()[0],
               'device_test_passed': True, 'missing_device_rejected': True,
               'physical_iphone': False, 'steamos': False, 'linux_gpu_shader_verified': False,
               'metal_verified': False, 'venus_transport_verified': False,
               'presentation_verified': False, 'gameplay_verified': False,
               'payload': metadata, 'device': device, 'missing_device': rejected}
    (payload / 'gpu-kernel-test.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=pathlib.Path)
    main(parser.parse_args().payload)
