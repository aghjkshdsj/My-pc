"""Synthetic identity/scope checks; fixtures are never phone measurements."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_device_report import validate_jit


class JITEvidenceTests(unittest.TestCase):
    def fixture(self):
        device = {'device_machine': 'iPhone-synthetic', 'ios_version': '27.0.1', 'os_build': 'fixture',
                  'host_page_bytes': 16384, 'code_signing': {'debugged': True, 'get_task_allow': True, 'debugger_attached': True}}
        return {'schema': 1, 'scope': 'physical-ios-host-probe', 'source_commit': 'fixture', 'build': 'fixture',
                'before': device, 'after': copy.deepcopy(device), 'tests': {'jit': {'status': 'passed', 'returned': 42,
                'execution': 'native-arm64-local-jit-stub', 'protocol': 'stikdebug-universal-prepared-rx-writable-alias',
                'linux_execution': False}}, 'acceptance': {k: False for k in ['linux_kernel_boot', 'steam_arm_client',
                'fex_game', 'linux_game_graphics_to_metal', 'steam_under_60_seconds', 'hollow_knight_60_to_80_base_fps']}}

    def check(self, row):
        return validate_jit(row, 'fixture', 'fixture', '27.0.1')

    def test_execution_keeps_linux_game_gates_false(self):
        result = self.check(self.fixture())
        self.assertTrue(result['native_arm64_jit_execution_verified'])
        self.assertFalse(result['linux_boot_verified'])

    def test_failed_or_fabricated_execution_rejected(self):
        for key, value in [('returned', 0), ('status', 'skipped'), ('execution', 'qemu-tcg'), ('linux_execution', True)]:
            row = self.fixture(); row['tests']['jit'][key] = value
            with self.assertRaises(ValueError): self.check(row)

    def test_mixed_or_stale_source_rejected(self):
        row = self.fixture(); row['source_commit'] = 'old'
        with self.assertRaises(ValueError): self.check(row)
        row = self.fixture(); row['after']['os_build'] = 'other'
        with self.assertRaises(ValueError): self.check(row)

    def test_missing_debugger_for_new_region_rejected(self):
        row = self.fixture(); row['before']['code_signing']['debugger_attached'] = False
        with self.assertRaises(ValueError): self.check(row)

    def test_claimed_linux_game_success_rejected(self):
        for key in ['linux_kernel_boot', 'steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal']:
            row = self.fixture(); row['acceptance'][key] = True
            with self.assertRaises(ValueError): self.check(row)


if __name__ == '__main__':
    unittest.main()
