#!/usr/bin/env python3
"""Synthetic rejection fixtures only; no fixture is physical phone evidence."""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_device_report import validate


class DeviceEvidenceTests(unittest.TestCase):
    def fixture(self):
        device = {'device_machine': 'iPhone-test-fixture', 'ios_version': '27.0.1',
                  'os_build': 'synthetic-fixture', 'host_page_bytes': 16384,
                  'code_signing': {'debugged': True}}
        guest = {'schema': 1, 'run': 'a' * 32, 'failures': 0, 'kernel': '6.12.111-fixture',
                 'machine': 'aarch64', 'elf_arch': 'aarch64', 'page_bytes': 4096, 'signals': True,
                 'mmap_protection': True, 'pthread_tls_futex': True, 'fork_exec': True,
                 'checksum': '1d250c45a7bbc87e', 'wall_ms': 8, 'cpu_ms': 7}
        linux = {'schema': 1, 'scope': 'physical-ios-linux-tcg-gate', 'source_commit': 'test-commit',
                 'payload': {'synthetic': True}, 'status': 'passed', 'linux_execution': True,
                 'engine_finished': True, 'engine_status': 0, 'engine': 'qemu-10.0.12-utm-aarch64-tcg',
                 'hardware_virtualization': False, 'steamos': False, 'graphics_tested': False,
                 'device': device, 'after': copy.deepcopy(device), 'run': guest['run'], 'guest': guest,
                 'serial_tail': 'MPC_LINUX_ABI ' + json.dumps(guest) + '\nMPC_LINUX_EXIT=0\n', 'elapsed_ms': 50}
        return {'schema': 1, 'scope': 'physical-ios-host-probe', 'source_commit': 'test-commit',
                'build': 'test-build', 'before': copy.deepcopy(device), 'after': copy.deepcopy(device),
                'tests': {'linux': linux}, 'acceptance': {'linux_kernel_boot': True,
                'steam_arm_client': False, 'fex_game': False, 'linux_game_graphics_to_metal': False,
                'steam_under_60_seconds': False, 'hollow_knight_60_to_80_base_fps': False}}

    def check(self, row):
        return validate(row, 'test-commit', 'test-build', {'synthetic': True}, '27.0.1')

    def test_valid_synthetic_schema_keeps_product_gates_false(self):
        row = self.check(self.fixture())
        self.assertFalse(row['steamos_verified'])
        self.assertFalse(row['guest_graphics_to_metal_verified'])
        self.assertFalse(row['cryptographic_device_attestation'])

    def test_hosted_scope_rejected(self):
        row = self.fixture(); row['tests']['linux']['scope'] = 'hosted-linux-tcg-kernel-test'
        with self.assertRaises(ValueError): self.check(row)

    def test_source_and_payload_rejected(self):
        for key, value in [('source_commit', 'old-commit'), ('payload', {'different': True})]:
            row = self.fixture(); row['tests']['linux'][key] = value
            with self.assertRaises(ValueError): self.check(row)

    def test_unfinished_failed_engine_rejected(self):
        for key, value in [('status', 'timed-out-engine-still-running'), ('engine_finished', False),
                           ('engine_status', 1), ('linux_execution', False)]:
            row = self.fixture(); row['tests']['linux'][key] = value
            with self.assertRaises(ValueError): self.check(row)

    def test_mixed_os_identity_rejected(self):
        row = self.fixture(); row['after']['os_build'] = 'different-build'
        with self.assertRaises(ValueError): self.check(row)

    def test_nonce_and_duplicate_serial_rejected(self):
        for change in ('nonce', 'duplicate'):
            row = self.fixture(); linux = row['tests']['linux']
            if change == 'nonce': linux['run'] = 'b' * 32
            else: linux['serial_tail'] += linux['serial_tail']
            with self.assertRaises(ValueError): self.check(row)

    def test_game_and_virtualization_claims_rejected(self):
        row = self.fixture(); row['acceptance']['fex_game'] = True
        with self.assertRaises(ValueError): self.check(row)
        row = self.fixture(); row['tests']['linux']['hardware_virtualization'] = True
        with self.assertRaises(ValueError): self.check(row)

    def test_invalid_timing_rejected(self):
        row = self.fixture(); row['tests']['linux']['elapsed_ms'] = float('nan')
        with self.assertRaises(ValueError): self.check(row)


if __name__ == '__main__':
    unittest.main()
