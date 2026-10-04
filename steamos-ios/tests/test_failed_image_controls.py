"""Failed-image control fixtures; they can never accept image import or games."""
import json
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_guest_gpu_report import validate
import test_guest_gpu_report as gpu_fixtures
from test_guest_metal_trace import fixture as metal_fixture

def fixture():
    report = gpu_fixtures.GuestGPUReportTests().fixture()
    gate = report['tests'].pop('linux_gpu')
    nonce = gate['run']
    trace = metal_fixture(); trace['run'] = nonce
    rejection = dict(schema=1, run=nonce, stage='linear-rgba8-export-properties', code=-11,
                     host_memory_import_verified=False, presentation_verified=False)
    capability = dict(schema=1, run=nonce, result=-11, external_features=0, compatible_handles=0,
                      max_width=0, max_height=0)
    native = dict(run=nonce, active=False, reading=False, events=[], images=[], errors=0,
                  diagnostic_full_image_readbacks=0)
    gate.update(scope='physical-ios-linux-guest-image-gate', status='failed', image_import_requested=True,
        display_backend_registered=True, host_private_file_directory_prepared=True,
        host_metal_completion_observer_requested=True, metal_host_verified=True, native_metal_trace=trace)
    gate['device']['metal_device'] = 'Apple fixture'
    gate['image_import'] = dict(scope='physical-ios-linux-guest-image-import-gate', run=nonce,
        host_memory_import_verified=False, presentation_verified=False, zero_copy_transport_verified=False,
        gameplay_verified=False, native=native, guest_rejections=[rejection], guest_producers=[], guest_exits=[])
    gate['serial_tail'] += ('MPC_IMAGE_CAPABILITIES ' + json.dumps(capability) + '\nMPC_IMAGE_REJECTED ' +
                            json.dumps(rejection) + '\nMPC_IMAGE_GUEST_EXIT=21\n')
    report.update(build='4000017', executed_tests=['linux_image'])
    report['tests']['linux_image'] = gate
    report['acceptance'].update(linux_guest_image_import=False, linux_guest_offscreen_metal_completion=True)
    return report

def check(report, **kwargs):
    return validate(report, 'test-commit', '4000017', {'synthetic': True},
        {'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}}, '27.0.1', **kwargs)

class FailedImageControlTests(unittest.TestCase):
    def test_only_controls_pass_and_full_import_remains_rejected(self):
        report = fixture()
        result = check(report, image_control_only=True)
        self.assertTrue(result['failed_image_controls_only'])
        self.assertTrue(result['metal_host_verified'])
        for key in ('host_memory_import_verified', 'presentation_verified', 'steamos_verified', 'gameplay_verified'):
            self.assertFalse(result[key])
        with self.assertRaises(ValueError): check(report, image_import=True)
        with self.assertRaises(ValueError): check(report, image_import=True, image_control_only=True)

    def test_stale_duplicate_and_invented_image_work_rejected(self):
        for mutation in ('nonce', 'duplicate', 'producer', 'native-work', 'success'):
            report = fixture(); gate = report['tests']['linux_image']
            if mutation == 'nonce': gate['serial_tail'] = gate['serial_tail'].replace('"result": -11', '"run": "old", "result": -11')
            if mutation == 'duplicate': gate['serial_tail'] += next(x for x in gate['serial_tail'].splitlines() if x.startswith('MPC_IMAGE_CAPABILITIES')) + '\n'
            if mutation == 'producer': gate['serial_tail'] += 'MPC_IMAGE_PRODUCER {}\n'
            if mutation == 'native-work': gate['image_import']['native']['diagnostic_full_image_readbacks'] = 1
            if mutation == 'success': gate['image_import']['host_memory_import_verified'] = True
            with self.assertRaises(ValueError): check(report, image_control_only=True)

    def test_missing_actual_linux_or_metal_controls_rejected(self):
        for key in ('engine_finished', 'linux_execution', 'guest_vulkan_pixels_verified', 'metal_host_verified'):
            report = fixture(); report['tests']['linux_image'][key] = False
            with self.assertRaises(ValueError): check(report, image_control_only=True)
        report = fixture(); report['tests']['linux_image']['native_metal_trace']['samples'] = []
        with self.assertRaises(ValueError): check(report, image_control_only=True)

    def test_partial_failure_cannot_pass_scope_or_status_inflation(self):
        for key, value in [('status', 'passed'), ('scope', 'physical-ios-linux-guest-vulkan-gate'),
                           ('host_memory_import_verified', True), ('presentation_verified', True)]:
            report = fixture(); report['tests']['linux_image'][key] = value
            with self.assertRaises(ValueError): check(report, image_control_only=True)
        report = fixture(); report['acceptance']['steam_arm_client'] = True
        with self.assertRaises(ValueError): check(report, image_control_only=True)

if __name__ == '__main__': unittest.main()
