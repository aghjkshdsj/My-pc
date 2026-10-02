"""Synthetic rejection checks; these fixtures are not phone measurements."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_device_report import validate_native_vulkan


class NativeVulkanEvidenceTests(unittest.TestCase):
    def fixture(self):
        device = {'device_machine': 'iPhone-fixture', 'ios_version': '27.0.1', 'os_build': 'fixture', 'host_page_bytes': 16384}
        draw = {'machine': 'iPhone-fixture', 'software': False, 'vendor_id': 0x106b, 'device_type': 1,
                'width': 1280, 'height': 720, 'shader_phases': 2, 'pixels_checked': 1843200,
                'mismatches': 0, 'channel_sum': 1219256320, 'validation_errors': 0, 'validation_enabled': False}
        return {'schema': 1, 'scope': 'physical-ios-host-probe', 'source_commit': 'fixture', 'build': 'fixture',
                'before': device, 'after': copy.deepcopy(device), 'tests': {'native_vulkan': {
                'scope': 'physical-ios-native-vulkan-offscreen-gate', 'status': 'passed', 'exit_status': 0,
                'native_vulkan_to_metal_verified': True, 'payload': {'fixture': True, 'engine_text_section': {'bytes': 1, 'sha256': 'fixture'}}, 'elapsed_ms': 1,
                'engine_text_section_matches': True, 'engine_text_section': {'bytes': 1, 'sha256': 'fixture'},
                'path': 'native-ios-arm64-vulkan-MoltenVK-Metal-offscreen', 'diagnostic': draw,
                'linux_graphics': False, 'presentation_verified': False, 'gameplay_verified': False}},
                'acceptance': dict(native_vulkan_to_metal_offscreen=True, steam_arm_client=False, fex_game=False,
                linux_game_graphics_to_metal=False, steam_under_60_seconds=False, hollow_knight_60_to_80_base_fps=False)}

    def check(self, row):
        return validate_native_vulkan(row, 'fixture', 'fixture', {'fixture': True, 'engine_text_section': {'bytes': 1, 'sha256': 'fixture'}}, '27.0.1')

    def test_valid_fixture_keeps_guest_and_game_gates_false(self):
        result = self.check(self.fixture())
        self.assertTrue(result['native_vulkan_to_metal_offscreen_verified'])
        self.assertFalse(result['linux_graphics_to_metal_verified'])
        self.assertFalse(result['validation_layer_observed'])

    def test_bad_pixels_or_software_rejected(self):
        for key, value in [('mismatches', 1), ('channel_sum', 0), ('software', True), ('device_type', 4), ('shader_phases', 1)]:
            row = self.fixture(); row['tests']['native_vulkan']['diagnostic'][key] = value
            with self.assertRaises(ValueError): self.check(row)

    def test_stale_engine_source_or_device_rejected(self):
        row = self.fixture(); row['tests']['native_vulkan']['payload'] = {}
        with self.assertRaises(ValueError): self.check(row)
        row = self.fixture(); row['source_commit'] = 'old'
        with self.assertRaises(ValueError): self.check(row)
        row = self.fixture(); row['after']['os_build'] = 'other'
        with self.assertRaises(ValueError): self.check(row)

    def test_aborted_or_unexecuted_draw_rejected(self):
        for key, value in [('status', 'failed'), ('exit_status', 3), ('native_vulkan_to_metal_verified', False)]:
            row = self.fixture(); row['tests']['native_vulkan'][key] = value
            with self.assertRaises(ValueError): self.check(row)

    def test_native_result_cannot_promote_product_gates(self):
        for key in ['steam_arm_client', 'fex_game', 'linux_game_graphics_to_metal', 'hollow_knight_60_to_80_base_fps']:
            row = self.fixture(); row['acceptance'][key] = True
            with self.assertRaises(ValueError): self.check(row)

    def test_exit_zero_without_complete_draw_receipt_is_rejected(self):
        row = self.fixture(); row['tests']['native_vulkan']['diagnostic'] = {}
        with self.assertRaises(ValueError): self.check(row)
        for key in ('machine', 'vendor_id', 'pixels_checked', 'mismatches', 'channel_sum'):
            row = self.fixture(); del row['tests']['native_vulkan']['diagnostic'][key]
            with self.assertRaises(ValueError): self.check(row)
