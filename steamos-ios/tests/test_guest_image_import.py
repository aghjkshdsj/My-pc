"""Image ownership/fence rejection fixtures, never phone acceptance."""
import copy
import json
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_guest_image_import import validate


def fixture():
    nonce = 'a' * 32
    producers, images, events = [], [], []
    for index, phase in enumerate((0, 41)):
        resource, generation = index + 12, index + 1
        producers.append(dict(schema=1, run=nonce, phase=phase, resource_id=resource, width=1280, height=720,
            tiling='drm-format-modifier', drm_modifier=0, memory_plane=0,
            row_pitch=5120, offset=0, allocation_bytes=3686400, producer_fence_completed=True, external_queue_release=True))
        images.append(dict(phase=phase, resource_id=resource, generation=generation, width=1280, height=720,
            row_pitch=5120, offset=0, backing_bytes=3686400, linear_alignment=64, native_pixel_format=70,
            native_registry_id=77, native_device='Apple fixture', native_buffer_alias_verified=True,
            pixels_checked=921600, mismatches=0, channel_sum=603566080 if phase else 615690240,
            consumer_status=4, consumer_error=False, gpu_start_seconds=1.0, gpu_end_seconds=1.001))
        for kind in (1, 2, 3): events.append(dict(kind=kind, sequence=len(events)+1, generation=generation, resource_id=resource))
    exit = dict(schema=1, run=nonce, status=0, phases=2, scanout_disabled=True, images_released=True, presentation_verified=False)
    native = dict(scope='native-metal-linux-linear-image-import', run=nonce, errors=0, active=False, reading=False,
        registry_id=77, diagnostic_full_image_readbacks=2, presentation_verified=False, zero_copy_transport_verified=False,
        events=events, images=images)
    receipt = dict(schema=1, scope='physical-ios-linux-guest-image-import-gate', run=nonce, host_memory_import_verified=True,
        presentation_verified=False, zero_copy_transport_verified=False, gameplay_verified=False, native=native,
        guest_producers=producers, guest_exits=[exit], guest_rejections=[], pixels_checked=1843200, channel_sum=1219256320)
    gate = dict(image_import_requested=True, image_import=receipt, native_metal_trace=dict(samples=[dict(device_registry_id=77)]))
    return gate, nonce


def serial(gate):
    r = gate['image_import']
    lines = ['MPC_IMAGE_PRODUCER ' + json.dumps(x) for x in r['guest_producers']]
    lines += ['MPC_IMAGE_EXIT ' + json.dumps(x) for x in r['guest_exits']]
    lines += ['MPC_IMAGE_REJECTED ' + json.dumps(x) for x in r['guest_rejections']]
    return '\n'.join(lines) + '\nMPC_IMAGE_GUEST_EXIT=0\n'


class GuestImageImportTests(unittest.TestCase):
    def check(self, gate, nonce): return validate(gate, serial(gate), nonce, 'Apple fixture')

    def test_fenced_correlated_fixture_does_not_claim_presentation_or_games(self):
        gate, nonce = fixture()
        result = self.check(gate, nonce)
        self.assertTrue(result['host_memory_import_verified'])
        for key in ('presentation_verified', 'gameplay_verified', 'zero_copy_transport_verified', 'cryptographic_device_attestation'):
            self.assertFalse(result[key])

    def test_modifier_required_for_new_guest_and_bad_or_missing_modifier_rejected(self):
        gate, nonce = fixture()
        validate(gate, serial(gate), nonce, 'Apple fixture', require_modifier=True)
        for key, value in [('tiling', 'linear-legacy'), ('drm_modifier', 1), ('memory_plane', 1), ('drm_modifier', None)]:
            gate, nonce = fixture(); gate['image_import']['guest_producers'][0][key] = value
            with self.assertRaises(ValueError): validate(gate, serial(gate), nonce, 'Apple fixture', require_modifier=True)

    def test_bgra_primary_plane_contract_requires_every_format_boundary(self):
        gate, nonce = fixture()
        for p in gate['image_import']['guest_producers']:
            p.update(vulkan_format=44, drm_fourcc=875713112, virtio_format=2, channel_order='bgra')
        for image in gate['image_import']['native']['images']:
            image.update(native_pixel_format=80, virtio_format=2, channel_order='bgra')
        validate(gate, serial(gate), nonce, 'Apple fixture', require_modifier=True, require_bgra=True)
        for target, key, wrong in [('guest_producers', 'vulkan_format', 37), ('guest_producers', 'drm_fourcc', 875708993),
                                  ('guest_producers', 'virtio_format', 67), ('guest_producers', 'channel_order', 'rgba'),
                                  ('images', 'native_pixel_format', 70), ('images', 'virtio_format', 1),
                                  ('images', 'channel_order', 'rgba')]:
            for value in (wrong, None):
                bad = copy.deepcopy(gate)
                rows = bad['image_import']['native']['images'] if target == 'images' else bad['image_import'][target]
                rows[0][key] = value
                with self.assertRaises(ValueError):
                    validate(bad, serial(bad), nonce, 'Apple fixture', require_modifier=True, require_bgra=True)

    def test_missing_or_stale_producer_fences_and_export_layout_rejected(self):
        for key, value in [('producer_fence_completed', False), ('external_queue_release', False),
                           ('run', 'old'), ('phase', 0), ('row_pitch', 1), ('offset', 3686400),
                           ('allocation_bytes', 1), ('resource_id', 12)]:
            gate, nonce = fixture(); gate['image_import']['guest_producers'][1][key] = value
            with self.assertRaises(ValueError): self.check(gate, nonce)

    def test_native_alias_pixels_device_and_completion_rejected(self):
        for key, value in [('mismatches', 1), ('consumer_status', 3), ('consumer_error', True),
                           ('native_registry_id', 88), ('native_buffer_alias_verified', False),
                           ('row_pitch', 10240), ('generation', 1), ('backing_bytes', 1),
                           ('linear_alignment', 3), ('channel_sum', 0), ('gpu_end_seconds', 0.5)]:
            gate, nonce = fixture(); gate['image_import']['native']['images'][1][key] = value
            with self.assertRaises(ValueError): self.check(gate, nonce)

    def test_ownership_missing_duplicate_or_stale_rejected(self):
        for index, key, value in [(0, 'kind', 2), (1, 'resource_id', 99), (2, 'kind', 1),
                                  (3, 'generation', 1), (4, 'sequence', 3), (5, 'kind', 2)]:
            gate, nonce = fixture(); gate['image_import']['native']['events'][index][key] = value
            with self.assertRaises(ValueError): self.check(gate, nonce)
        gate, nonce = fixture(); gate['image_import']['native']['events'] = []
        with self.assertRaises(ValueError): self.check(gate, nonce)

    def test_failed_cleanup_pending_consumer_or_scope_inflation_rejected(self):
        for key in ('images_released', 'scanout_disabled'):
            gate, nonce = fixture(); gate['image_import']['guest_exits'][0][key] = False
            with self.assertRaises(ValueError): self.check(gate, nonce)
        for key in ('reading', 'active', 'presentation_verified', 'zero_copy_transport_verified'):
            gate, nonce = fixture(); gate['image_import']['native'][key] = True
            with self.assertRaises(ValueError): self.check(gate, nonce)
        gate, nonce = fixture(); gate['image_import']['guest_rejections'] = [dict(stage='unsupported-export')]
        with self.assertRaises(ValueError): self.check(gate, nonce)

    def test_duplicate_exits_or_serial_disagreement_rejected(self):
        gate, nonce = fixture()
        for text in (serial(gate) + 'MPC_IMAGE_GUEST_EXIT=0\n', serial(gate).replace('"phase": 41', '"phase": 42')):
            with self.assertRaises(ValueError): validate(gate, text, nonce, 'Apple fixture')

    def test_complete_report_requires_fresh_image_gate_and_native_producer_control(self):
        from test_guest_gpu_report import GuestGPUReportTests
        from test_guest_metal_trace import fixture as metal_fixture
        from verify_guest_gpu_report import validate as validate_report
        report = GuestGPUReportTests().fixture()
        old_gate = report['tests'].pop('linux_gpu')
        image_gate, ignored_nonce = fixture()
        boot_nonce = old_gate['run']
        receipt = image_gate['image_import']
        receipt['run'] = receipt['native']['run'] = boot_nonce
        for row in receipt['guest_producers'] + receipt['guest_exits']: row['run'] = boot_nonce
        trace = metal_fixture(); trace['run'] = boot_nonce
        for sample in trace['samples']: sample['device_registry_id'] = 77
        old_gate.update(scope='physical-ios-linux-guest-image-gate', image_import_requested=True,
            image_import=receipt, host_memory_import_verified=True, display_backend_registered=True,
            host_private_file_directory_prepared=True, host_metal_completion_observer_requested=True,
            native_metal_trace=trace, metal_host_verified=True)
        old_gate['device']['metal_device'] = 'Apple fixture'
        old_gate['serial_tail'] += serial(image_gate)
        report.update(build='4000017', executed_tests=['linux_image'])
        report['tests']['linux_image'] = old_gate
        report['acceptance'].update(linux_guest_image_import=True, linux_guest_offscreen_metal_completion=True)
        def check():
            return validate_report(report, 'test-commit', '4000017', {'synthetic': True},
                {'engine_text_sections': {'fixture': {'sha256': 'not-a-device-result'}}}, '27.0.1', image_import=True)
        result = check()
        self.assertTrue(result['host_memory_import_verified'])
        self.assertFalse(result['presentation_verified'])
        for key in ('host_metal_completion_observer_requested', 'engine_finished'):
            old_gate[key] = False
            with self.assertRaises(ValueError): check()
            old_gate[key] = True
        report['executed_tests'] = ['linux_gpu']
        with self.assertRaises(ValueError): check()


if __name__ == '__main__': unittest.main()
