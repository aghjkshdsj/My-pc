"""Missing/stale actual presentation must fail; fixtures are not phone results."""
import copy
import math
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_guest_screen import validate


def fixture():
    nonce = 'a'*32
    images = [dict(resource_id=10, generation=1, phase=0), dict(resource_id=11, generation=3, phase=41)]
    frames = []
    for i, image in enumerate(images):
        t = i*2+1
        frames.append(dict(image, frame_index=i+1, source_registry_id=77, drawable_registry_id=77,
            source_is_imported_guest_texture=True, source_width=1280, source_height=720, source_pixel_format=80,
            drawable_pixel_format=80, geometry=1, gpu_completed=True, drawable_presented=True,
            consumer_status=4, consumer_error=False, drawable_id=i, drawable_width=1280, drawable_height=720,
            viewport=[0, 0, 1280, 720], submit_seconds=t, gpu_start_seconds=t+.001,
            gpu_end_seconds=t+.002, presented_seconds=t+.016))
    false_claims = dict(continuous_animation_verified=False, frame_pacing_verified=False,
                       zero_copy_transport_verified=False, gameplay_verified=False)
    native = dict(false_claims, schema=1, scope='native-metal-two-linux-image-screen', run=nonce, registry_id=77,
                  frames=frames, errors=0, pending=0, interrupted=False, surface_visible=True, surface_geometry=1,
                  maximum_inflight=1, drawable_limit=2, diagnostic_source_readbacks=2, drawable_cpu_readbacks=0)
    receipt = dict(false_claims, schema=1, scope='physical-ios-linux-two-image-screen-gate', run=nonce,
                   presentation_verified=True, native=native)
    gate = dict(screen_presentation_requested=True, presentation_verified=True, screen_presentation=receipt,
                image_import=dict(host_memory_import_verified=True, run=nonce, native=dict(registry_id=77, images=images)))
    return gate, nonce


class GuestScreenTests(unittest.TestCase):
    def test_two_callbacks_and_import_are_required_without_fps_claim(self):
        gate, nonce = fixture(); result = validate(gate, nonce)
        self.assertTrue(result['presentation_verified'])
        for k in ('continuous_animation_verified', 'frame_pacing_verified', 'gameplay_verified',
                  'zero_copy_transport_verified', 'cryptographic_device_attestation'):
            self.assertFalse(result[k])
        gate['image_import']['host_memory_import_verified'] = False
        with self.assertRaises(ValueError): validate(gate, nonce)

    def test_missing_wrong_or_dropped_screen_callbacks_fail(self):
        wrong = dict(frame_index=3, resource_id=99, generation=9, phase=0, source_registry_id=88,
                     drawable_registry_id=88, source_is_imported_guest_texture=False, source_width=1279,
                     source_height=719, source_pixel_format=70, drawable_pixel_format=70, geometry=2,
                     gpu_completed=False, drawable_presented=False, consumer_status=5, consumer_error=True,
                     drawable_width=0, drawable_height=0, drawable_id=-1, presented_seconds=0,
                     gpu_start_seconds=0, gpu_end_seconds=0, submit_seconds=0, viewport=[0, 0, 720, 1280])
        for key, value in wrong.items():
            for missing in (False, True):
                gate, nonce = fixture(); frame = gate['screen_presentation']['native']['frames'][1]
                if missing: frame.pop(key)
                else: frame[key] = value
                with self.subTest(key=key, missing=missing), self.assertRaises(ValueError): validate(gate, nonce)

    def test_background_overflow_unfinished_and_unsupported_claims_fail(self):
        wrong = dict(errors=1, pending=1, interrupted=True, surface_visible=False, maximum_inflight=3,
                     drawable_limit=3, diagnostic_source_readbacks=0, drawable_cpu_readbacks=1,
                     continuous_animation_verified=True, frame_pacing_verified=True,
                     zero_copy_transport_verified=True, gameplay_verified=True, run='old', registry_id=88)
        for key, value in wrong.items():
            gate, nonce = fixture(); gate['screen_presentation']['native'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(gate, nonce)

    def test_reordered_duplicate_mixed_nonce_and_nonfinite_timestamps_fail(self):
        for mutation in ('reverse', 'duplicate', 'missing', 'nonce', 'early-display', 'nan', 'inf'):
            gate, nonce = fixture(); receipt = gate['screen_presentation']; frames = receipt['native']['frames']
            if mutation == 'reverse': frames.reverse()
            elif mutation == 'duplicate': frames[1] = copy.deepcopy(frames[0])
            elif mutation == 'missing': frames.pop()
            elif mutation == 'nonce': receipt['run'] = 'old'
            elif mutation == 'early-display': frames[1]['presented_seconds'] = 1
            elif mutation == 'nan': frames[1]['gpu_start_seconds'] = math.nan
            elif mutation == 'inf': frames[1]['presented_seconds'] = math.inf
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(gate, nonce)

    def test_portrait_letterbox_and_drawable_id_reuse_are_valid(self):
        gate, nonce = fixture()
        for f in gate['screen_presentation']['native']['frames']:
            f.update(drawable_width=720, drawable_height=1280, drawable_id=0, viewport=[0, 437.5, 720, 405])
        self.assertTrue(validate(gate, nonce)['presentation_verified'])
