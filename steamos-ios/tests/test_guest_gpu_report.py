"""Rejection fixtures only; these are not phone, shader or host Metal evidence."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_guest_gpu_report import validate, unpack_private
import test_device_evidence


class GuestGPUReportTests(unittest.TestCase):
    def fixture(self):
        report = test_device_evidence.DeviceEvidenceTests().fixture()
        gate = report['tests'].pop('linux')
        report['tests']['linux_gpu'] = gate
        report['executed_tests'] = ['linux_gpu']
        gate.update(scope='physical-ios-linux-guest-vulkan-gate', graphics_tested=True,
                    engine_bundle={'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}},
                    engine_text_sections_verified=True,
                    engine_text_sections_observed={'fixture': {'sha256': 'not-a-device-result'}},
                    guest_gpu_device_requested=True, guest_gpu_host_visible_mib=128,
                    requested_jit_cache_mib=32, split_wx_requested=True,
                    fresh_guest_vulkan_nonce_bound=True, graphics_kernel_device_detected=True,
                    guest_vulkan_pixels_verified=True, metal_host_verified=False,
                    host_memory_import_verified=False, presentation_verified=False, gameplay_verified=False)
        gpu = {'run': gate['run'], 'driver': 'virtio_gpu', 'page_bytes': 4096,
               'parameters': {k: {'supported': True, 'value': 1} for k in ('1','3','4','6')}}
        draw = {'machine': 'aarch64', 'software': False, 'width': 1280, 'height': 720, 'shader_phases': 2,
                'pixels_checked': 1843200, 'mismatches': 0, 'channel_sum': 1219256320, 'validation_errors': 0,
                'metal_host_verified': False, 'presentation_verified': False, 'game_fps_verified': False}
        gate['graphics_kernel'], gate['guest_vulkan'] = gpu, draw
        gate['serial_tail'] = ('MPC_GPU_GUEST_RUN=' + gate['run'] + '\n' + gate['serial_tail'] +
            'MPC_GPU_KERNEL ' + json.dumps(gpu) + '\nMPC_VK_DIAGNOSTIC ' + json.dumps(draw) + '\nMPC_GPU_GUEST_EXIT=0\n')
        report['acceptance']['linux_guest_vulkan_pixels'] = True
        return report

    def check(self, report):
        return validate(report, 'test-commit', 'test-build', {'synthetic': True},
                        {'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}}, '27.0.1')

    def correlate_serial(self, report):
        # Keep bad semantic fields consistent in both copies, so rejection
        # must test capabilities/pixels rather than only serial disagreement.
        gate=report['tests']['linux_gpu']; lines=[]
        for line in gate['serial_tail'].splitlines():
            if line.startswith('MPC_GPU_KERNEL '): line='MPC_GPU_KERNEL '+json.dumps(gate['graphics_kernel'])
            if line.startswith('MPC_VK_DIAGNOSTIC '): line='MPC_VK_DIAGNOSTIC '+json.dumps(gate['guest_vulkan'])
            lines.append(line)
        gate['serial_tail']='\n'.join(lines)+'\n'

    def test_scoped_fixture_never_establishes_host_or_game_proof(self):
        result = self.check(self.fixture())
        self.assertTrue(result['guest_vulkan_pixels_receipt_valid'])
        for key in ('metal_host_verified', 'host_memory_import_verified', 'presentation_verified',
                    'gameplay_verified', 'steamos_verified', 'cryptographic_device_attestation'):
            self.assertFalse(result[key])

    def test_private_namespace_preparation_required_for_build_4000014(self):
        def check(row):
            return validate(row, 'test-commit', '4000014', {'synthetic': True},
                            {'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}}, '27.0.1')
        row = self.fixture(); row['build'] = '4000014'
        gate = row['tests']['linux_gpu']; gate['display_backend_registered'] = True
        for value in [None, False, 1, 'true']:
            gate['host_private_file_directory_prepared'] = value
            with self.assertRaises(ValueError): check(row)
        gate['host_private_file_directory_prepared'] = True
        result = check(row)
        self.assertTrue(result['guest_vulkan_pixels_receipt_valid'])
        self.assertFalse(result['host_memory_import_verified'])
        self.assertFalse(result['presentation_verified'])

    def test_stale_cached_or_mixed_engine_rejected(self):
        for key, value in [('executed_tests', ['jit']), ('source_commit', 'old'), ('build', 'old')]:
            row=self.fixture(); row[key]=value
            with self.assertRaises(ValueError): self.check(row)
        row=self.fixture(); row['tests']['linux_gpu']['engine_text_sections_observed']={}
        with self.assertRaises(ValueError): self.check(row)

    def test_observer_builds_require_native_completion_and_scoped_acceptance(self):
        for build in ('4000015', '4000016'):
            self.check_observer_build(build)

    def check_observer_build(self, build):
        from test_guest_metal_trace import fixture as metal_fixture
        row=self.fixture(); row['build']=build
        gate=row['tests']['linux_gpu']; gate['device']['metal_device']='Apple fixture'
        gate.update(display_backend_registered=True,host_private_file_directory_prepared=True,
                    host_metal_completion_observer_requested=True,metal_host_verified=True)
        trace=metal_fixture(); trace['run']=gate['run']; gate['native_metal_trace']=trace
        row['acceptance']['linux_guest_offscreen_metal_completion']=True
        def check(): return validate(row,'test-commit',build,{'synthetic':True},
            {'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}},'27.0.1')
        result=check(); self.assertTrue(result['metal_host_verified'])
        self.assertFalse(result['presentation_verified']); self.assertFalse(result['gameplay_verified'])
        for field in ('metal_host_verified','host_metal_completion_observer_requested'):
            gate[field]=False
            with self.assertRaises(ValueError): check()
            gate[field]=True
        gate['native_metal_trace']=None
        with self.assertRaises(ValueError): check()
        gate['native_metal_trace']=trace
        row['acceptance']['linux_guest_offscreen_metal_completion']=False
        with self.assertRaises(ValueError): check()

    def test_pixels_capabilities_and_scope_inflation_rejected(self):
        for field, value in [('software',True), ('mismatches',1), ('channel_sum',0), ('metal_host_verified',True)]:
            row=self.fixture(); row['tests']['linux_gpu']['guest_vulkan'][field]=value
            self.correlate_serial(row)
            with self.assertRaises(ValueError): self.check(row)
        row=self.fixture(); row['tests']['linux_gpu']['graphics_kernel']['parameters']['4']['value']=0
        self.correlate_serial(row)
        with self.assertRaises(ValueError): self.check(row)
        row=self.fixture(); row['tests']['linux_gpu']['host_memory_import_verified']=True
        with self.assertRaises(ValueError): self.check(row)

    def test_duplicate_nonce_markers_and_failed_boot_rejected(self):
        for tail in ('MPC_GPU_GUEST_RUN=' + 'b'*32 + '\n', 'MPC_GPU_GUEST_EXIT=0\n', 'MPC_VK_DIAGNOSTIC invalid\n'):
            row=self.fixture(); row['tests']['linux_gpu']['serial_tail']+=tail
            with self.assertRaises(ValueError): self.check(row)
        row=self.fixture(); row['tests']['linux_gpu']['engine_finished']=False
        with self.assertRaises(ValueError): self.check(row)

    def test_recovery_requires_complete_matching_serial(self):
        report=self.fixture(); nonce=report['tests']['linux_gpu']['run']
        recovery={'scope':'private-ios-interrupted-probe-diagnostics','files':[
            {'name':'result.json','tail_truncated':False,'text':json.dumps(report)},
            {'name':'serial.log','relative_directory':'LinuxGate-'+nonce,'tail_truncated':False,
             'text':report['tests']['linux_gpu']['serial_tail']}]}
        parsed, serial=unpack_private(recovery)
        self.assertEqual(parsed,report); self.assertEqual(serial,report['tests']['linux_gpu']['serial_tail'])
        older=self.fixture(); older['source_commit']='old'
        recovery['files'].append({'name':'older-result.json','tail_truncated':False,'text':json.dumps(older)})
        self.assertEqual(unpack_private(recovery,'test-commit','test-build')[0],report)
        recovery['files'][1]['tail_truncated']=True
        with self.assertRaises(ValueError): unpack_private(recovery,'test-commit','test-build')
        with self.assertRaises(ValueError): unpack_private({'scope':recovery['scope'],'files':[]})

    def test_corrected_build_requires_observed_backend_registration(self):
        row=self.fixture(); row['build']='4000012'
        gate=row['tests']['linux_gpu']; gate['display_backend_registered']=True
        bundle={'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}}
        validate(row,'test-commit','4000012',{'synthetic':True},bundle,'27.0.1')
        del gate['display_backend_registered']
        with self.assertRaises(ValueError): validate(row,'test-commit','4000012',{'synthetic':True},bundle,'27.0.1')


if __name__ == '__main__':
    unittest.main()
