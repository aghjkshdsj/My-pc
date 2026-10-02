"""Reject misleading graphics receipts even when the pixel check succeeded."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_graphics_diagnostic import validate


class GraphicsEvidenceTests(unittest.TestCase):
    def row(self):
        return {'machine': 'aarch64', 'width': 1280, 'height': 720, 'shader_phases': 2,
                'pixels_checked': 1843200, 'mismatches': 0, 'channel_sum': 1219256320,
                'software': True, 'device_type': 4, 'renderer': 'llvmpipe test fixture',
                'validation_enabled': True, 'synchronization_validation_requested': True,
                'validation_errors': 0, 'metal_host_verified': False,
                'presentation_verified': False, 'game_fps_verified': False,
                'device_extensions': ['VK_KHR_fixture']}

    def check(self, row, code=20, text=None):
        return validate(row, code, text or 'MPC_VK_REJECTED software_renderer=' + row['renderer'])

    def test_valid_fixture(self):
        self.check(self.row())

    def test_false_claims_and_bad_pixels(self):
        for key, value in [('machine', 'x86_64'), ('pixels_checked', 1), ('channel_sum', 0),
                           ('mismatches', 1), ('validation_errors', 1), ('software', False),
                           ('metal_host_verified', True), ('presentation_verified', True),
                           ('game_fps_verified', True), ('validation_enabled', False)]:
            with self.subTest(key=key):
                row = copy.deepcopy(self.row()); row[key] = value
                with self.assertRaises(AssertionError): self.check(row)

    def test_wrong_rejection_code_or_device(self):
        with self.assertRaises(AssertionError): self.check(self.row(), code=0)
        with self.assertRaises(AssertionError): self.check(self.row(), text='MPC_VK_REJECTED software_renderer=other')


if __name__ == '__main__':
    unittest.main()
