"""Production native completion rejection fixtures, not actual GPU evidence."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_guest_metal_trace import validate


def fixture():
    return {'schema': 1, 'scope': 'native-moltenvk-guest-command-completion', 'abi': 1,
            'run': 'fixture-nonce', 'status': 'passed', 'expected_device_name': 'Apple fixture',
            'callback_source': 'MVKQueueCommandBufferSubmission::commitActiveMTLCommandBuffer',
            'observer_configured': True, 'callbacks_drained': True, 'guest_pixels_passed': True,
            'metal_host_verified': True, 'adds_gpu_work': False, 'host_memory_import_verified': False,
            'presentation_verified': False, 'gameplay_verified': False,
            **{k: 0 for k in ('pending','failed','overflow','unknown_callbacks','duplicate_callbacks',
                             'identity_errors','initial_errors','invalid_timing')},
            'observed_commit_points': 2, 'completed': 2, 'timed_completions': 2,
            'samples': [{'token': i, 'device_registry_id': 99, 'device_name': 'Apple fixture',
                         'completion_observed': True, 'status': 4, 'has_error': False, 'error_code': 0,
                         'gpu_start_seconds': 3.0 + i, 'gpu_end_seconds': 3.01 + i} for i in (1,2)]}


class GuestMetalTraceTests(unittest.TestCase):
    def check(self, row): return validate(row, 'fixture-nonce', 'Apple fixture')
    def test_fixture_has_no_import_presentation_game_or_attestation_proof(self):
        result=self.check(fixture()); self.assertTrue(result['metal_host_verified'])
        for key in ('host_memory_import_verified','presentation_verified','gameplay_verified','cryptographic_device_attestation'):
            self.assertFalse(result[key])
    def test_stale_wrong_scope_or_source_rejected(self):
        for key,value in [('run','stale'),('scope','native-demo'),('callback_source','waitIdle'),('expected_device_name','different')]:
            row=fixture();row[key]=value
            with self.assertRaises(ValueError): self.check(row)
    def test_unfinished_failed_missing_or_boolean_counts_rejected(self):
        for key in ('pending','failed','overflow','unknown_callbacks','duplicate_callbacks','identity_errors','initial_errors','invalid_timing'):
            for value in (1,False,None):
                row=fixture();row[key]=value
                with self.assertRaises(ValueError): self.check(row)
        for key in ('observer_configured','callbacks_drained','guest_pixels_passed','metal_host_verified'):
            row=fixture();row[key]=False
            with self.assertRaises(ValueError): self.check(row)
    def test_missing_duplicate_status_error_or_device_rejected(self):
        for key,value in [('token',2),('status',3),('status',5),('status',True),('has_error',True),
                          ('completion_observed',False),('error_code',3),('device_registry_id',100),('device_name','different')]:
            row=fixture();row['samples'][0][key]=value
            with self.assertRaises(ValueError): self.check(row)
        for value in ([],[fixture()['samples'][0]],{}):
            row=fixture();row['samples']=value
            with self.assertRaises(ValueError): self.check(row)
    def test_invalid_timestamps_rejected(self):
        for value in (float('nan'),float('inf'),-1,True,None,0):
            row=fixture();row['samples'][0]['gpu_start_seconds']=value
            with self.assertRaises(ValueError): self.check(row)
        row=fixture();row['samples'][0]['gpu_end_seconds']=1
        with self.assertRaises(ValueError): self.check(row)
    def test_scope_inflation_and_count_disagreement_rejected(self):
        for key in ('adds_gpu_work','host_memory_import_verified','presentation_verified','gameplay_verified'):
            row=fixture();row[key]=True
            with self.assertRaises(ValueError): self.check(row)
        for key in ('observed_commit_points','completed','timed_completions'):
            row=fixture();row[key]=3
            with self.assertRaises(ValueError): self.check(row)
    def test_empty_marker_buffer_cannot_replace_timed_work(self):
        row=fixture();entry=copy.deepcopy(row['samples'][0]);entry.update(token=3,gpu_start_seconds=0,gpu_end_seconds=0)
        row['samples'].append(entry);row.update(observed_commit_points=3,completed=3)
        self.assertEqual(self.check(row)['timed_completions'],2)
        row['samples'][0].update(gpu_start_seconds=0,gpu_end_seconds=0);row['timed_completions']=1
        with self.assertRaises(ValueError): self.check(row)
    def test_equal_positive_timestamps_do_not_count_as_timed_work(self):
        row=fixture();entry=copy.deepcopy(row['samples'][0])
        entry.update(token=3,gpu_start_seconds=7.0,gpu_end_seconds=7.0)
        row['samples'].append(entry);row.update(observed_commit_points=3,completed=3)
        result=self.check(row)
        self.assertEqual(result['native_command_completions'],3)
        self.assertEqual(result['timed_completions'],2)
        row['samples'][0].update(gpu_start_seconds=4.0,gpu_end_seconds=4.0)
        row['timed_completions']=1
        with self.assertRaises(ValueError): self.check(row)


if __name__ == '__main__': unittest.main()
