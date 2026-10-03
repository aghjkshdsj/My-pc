"""Reject replay, missing-device and scope inflation in kernel-only evidence."""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from run_gpu_kernel_gate import validate

NONCE = '0123456789abcdef0123456789abcdef'


def receipt():
    abi = {'schema': 1, 'run': NONCE, 'failures': 0, 'machine': 'aarch64', 'elf_arch': 'aarch64',
           'page_bytes': 4096, 'signals': True, 'mmap_protection': True, 'pthread_tls_futex': True,
           'fork_exec': True, 'checksum': '1d250c45a7bbc87e', 'wall_ms': 4.0, 'cpu_ms': 3.8}
    gpu = {'schema': 1, 'scope': 'linux-virtio-gpu-kernel-device', 'run': NONCE,
           'machine': 'aarch64', 'page_bytes': 4096, 'kernel': '6.12.111', 'wall_ms': 2.0,
           'driver': 'virtio_gpu', 'stage': 'complete', 'exit_code': 0, 'errno': 0, 'mismatches': 0,
           'width': 1280, 'height': 720, 'mapped_bytes': 3686400, 'mapped_sum': 470016000,
           'mapped_resource_verified': True, 'transfer_ioctl_completed': True, 'resource_closed': True,
           'parameters': {str(i): {'supported': True, 'value': int(i == 2)} for i in range(1, 9)}}
    gpu['resource_bind_flags'] = 2
    gpu.update({name: False for name in ['gpu_shader_verified', 'host_pixels_verified',
                                        'metal_verified', 'presentation_verified', 'gameplay_verified']})
    return abi, gpu


def serial(abi, gpu):
    return ('MPC_LINUX_ABI ' + json.dumps(abi) + '\nMPC_GPU_KERNEL ' + json.dumps(gpu) +
            '\nMPC_LINUX_EXIT=0\nMPC_GPU_KERNEL_EXIT=' + str(gpu['exit_code']) + '\n')


class GPUKernelEvidence(unittest.TestCase):
    def test_kernel_only_scope(self):
        abi, gpu = receipt()
        result = validate(serial(abi, gpu), NONCE, True)
        self.assertTrue(result['kernel_gpu']['mapped_resource_verified'])
        self.assertFalse(result['kernel_gpu']['metal_verified'])

    def test_replay_and_duplicate(self):
        abi, gpu = receipt()
        for changed in [dict(gpu, run='0' * 32), dict(gpu, mapped_sum=1), dict(gpu, wall_ms=float('nan')), dict(gpu, resource_bind_flags=0)]:
            with self.assertRaises(AssertionError):
                validate(serial(abi, changed), NONCE, True)
        with self.assertRaises(AssertionError):
            validate(serial(abi, gpu) + 'MPC_GPU_KERNEL ' + json.dumps(gpu), NONCE, True)

    def test_scope_inflation(self):
        abi, gpu = receipt()
        for name in ['gpu_shader_verified', 'host_pixels_verified', 'metal_verified', 'presentation_verified', 'gameplay_verified']:
            with self.subTest(name=name), self.assertRaises(AssertionError):
                validate(serial(abi, dict(gpu, **{name: True})), NONCE, True)
        changed = copy.deepcopy(gpu)
        changed['parameters']['1']['value'] = 1
        with self.assertRaises(AssertionError):
            validate(serial(abi, changed), NONCE, True)

    def test_missing_device_must_fail_positive_gate(self):
        abi, gpu = receipt()
        gpu.update(driver='', stage='open-drm', exit_code=1, errno=2,
                   mapped_resource_verified=False, transfer_ioctl_completed=False, resource_closed=False)
        validate(serial(abi, gpu), NONCE, False)
        with self.assertRaises(AssertionError):
            validate(serial(abi, gpu), NONCE, True)
        gpu['stage'] = 'complete'
        with self.assertRaises(AssertionError):
            validate(serial(abi, gpu), NONCE, False)


if __name__ == '__main__':
    unittest.main()
