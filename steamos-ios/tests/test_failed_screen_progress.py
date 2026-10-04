"""Failed display timestamps stay failed even with completed GPU work."""
import copy
import math
import unittest
from test_guest_screen import fixture
import test_guest_screen
from verify_failed_screen_progress import validate
from verify_guest_screen import validate as validate_passed


def failed_fixture():
    gate, nonce = fixture()
    gate.update(status='failed', presentation_verified=False)
    receipt = gate['screen_presentation']
    receipt.update(presentation_verified=False, reason='screen-presentation-acceptance-incomplete')
    receipt['native']['interrupted'] = True
    for frame in receipt['native']['frames']: frame['presented_seconds'] = 0
    return gate, nonce


class FailedScreenProgressTests(unittest.TestCase):
    def transaction_failure(self):
        gate, nonce = test_guest_screen.GuestScreenTests().transaction_fixture()
        gate.update(status='failed', presentation_verified=False)
        gate['screen_presentation'].update(presentation_verified=False, reason='screen-presentation-acceptance-incomplete')
        for frame in gate['screen_presentation']['native']['frames']:
            frame.update(presented_seconds=0, presented_seconds_later_query=0,
                gpu_completed_callback_seconds=frame['gpu_end_seconds']+.0001,
                later_query_host_seconds=frame['presented_callback_seconds']+.1)
        return gate, nonce

    def test_uninterrupted_transaction_still_does_not_accept_display_time(self):
        gate, nonce = self.transaction_failure()
        result = validate(gate, nonce, transaction=True)
        self.assertFalse(result['presentation_verified'])
        self.assertEqual(result['completed_screen_gpu_consumers'], 2)
        with self.assertRaises(ValueError): validate_passed(gate, nonce)

    def test_transaction_failure_requires_exact_original_route_and_zero_queries(self):
        for key,value in [('presented_seconds_later_query',3.1),('presentation_on_main_thread',False),
                          ('scheduled_status',5),('completion_join_retired',False),('later_query_host_seconds',0),
                          ('gpu_completed_callback_seconds',math.nan)]:
            gate,nonce=self.transaction_failure(); gate['screen_presentation']['native']['frames'][1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate(gate,nonce,transaction=True)
        gate,nonce=self.transaction_failure(); gate['screen_presentation']['native']['interrupted']=True
        with self.assertRaises(ValueError): validate(gate,nonce,transaction=True)

    def test_completed_gpu_work_never_establishes_display_or_fps(self):
        gate, nonce = failed_fixture(); result = validate(gate, nonce)
        self.assertEqual(result['completed_screen_gpu_consumers'], 2)
        for key in ('presentation_verified', 'continuous_animation_verified', 'frame_pacing_verified',
                    'gameplay_verified', 'zero_copy_transport_verified', 'cryptographic_device_attestation'):
            self.assertFalse(result[key])
        with self.assertRaises(ValueError): validate_passed(gate, nonce)

    def test_preserved_one_frame_attempt_is_separate_from_two_frame_attempt(self):
        gate, nonce = failed_fixture(); native = gate['screen_presentation']['native']
        native['frames'].pop(); native['errors'] = 1
        self.assertEqual(validate(gate, nonce)['completed_screen_gpu_consumers'], 1)
        native['errors'] = 0
        with self.assertRaises(ValueError): validate(gate, nonce)

    def test_status_scope_and_claim_inflation_fail(self):
        for key, value in [('status', 'passed'), ('presentation_verified', True), ('screen_presentation_requested', False)]:
            gate, nonce = failed_fixture(); gate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(gate, nonce)
        for key, value in [('run', 'old'), ('scope', 'other'), ('interrupted', False), ('pending', 1),
                           ('registry_id', 88), ('drawable_cpu_readbacks', 1), ('frame_pacing_verified', True)]:
            gate, nonce = failed_fixture(); gate['screen_presentation']['native'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(gate, nonce)

    def test_stale_source_missing_gpu_work_and_rewritten_display_time_fail(self):
        wrong = dict(resource_id=99, generation=2, phase=0, source_registry_id=88, source_width=720,
            source_is_imported_guest_texture=False, drawable_registry_id=88, geometry=2, gpu_completed=False,
            consumer_status=5, consumer_error=True, drawable_presented=False, drawable_id=-1,
            presented_seconds=3.1, gpu_start_seconds=0, gpu_end_seconds=math.nan, viewport=[0, 0, 720, 1280])
        for key, value in wrong.items():
            for missing in (False, True):
                gate, nonce = failed_fixture(); frame = gate['screen_presentation']['native']['frames'][1]
                if missing: frame.pop(key)
                else: frame[key] = value
                with self.subTest(key=key, missing=missing), self.assertRaises(ValueError): validate(gate, nonce)
        gate, nonce = failed_fixture(); frames = gate['screen_presentation']['native']['frames']
        frames[1] = copy.deepcopy(frames[0])
        with self.assertRaises(ValueError): validate(gate, nonce)
