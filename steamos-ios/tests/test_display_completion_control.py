import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_display_completion_control import validate

NONCE = '1234567890abcdef1234567890abcdef'


def fixture(case):
    missing = case == 'missing'
    abi = dict(schema=1, run=NONCE, failures=0, machine='aarch64', elf_arch='aarch64', page_bytes=4096,
               signals=True, mmap_protection=True, pthread_tls_futex=True, fork_exec=True,
               checksum='1d250c45a7bbc87e', wall_ms=2.0, cpu_ms=1.0)
    row = dict(schema=1, run=NONCE, case=case, stage='missing-response-held' if missing else 'complete',
               initial_status=1, early_pending=2 if case == 'delayed' else 1,
               events=0 if missing else (2 if case in ('delayed', 'producer-error') else 1),
               positive_fences=2 if case == 'delayed' else 0,
               error_fences=2 if case == 'producer-error' else (1 if case == 'error' else 0),
               last_status=0 if missing else (-5 if case in ('error', 'producer-error') else 1),
               buffers_retained=missing, cleaned=not missing, cpu_dumb_control=True,
               metal_verified=False, physical_iphone=False)
    return abi, row


def serial(abi, row):
    flushes = ''.join('MPC_CONTROL_FLUSH ' + json.dumps(dict(index=i, fence_id=10 + i)) + '\n'
                      for i in range(1, 4 if row['case'] == 'delayed' else 3))
    return 'MPC_LINUX_ABI ' + json.dumps(abi) + '\n' + flushes + 'MPC_COMPLETION_RESULT ' + json.dumps(row) + '\n' + (
        '' if row['case'] == 'missing' else 'MPC_COMPLETION_EXIT=0\nMPC_LINUX_EXIT=0\n')


class DisplayCompletionControls(unittest.TestCase):
    def test_complete_controls_are_only_hosted_cpu_evidence(self):
        for case in ('delayed', 'error', 'producer-error', 'missing'):
            result = validate(serial(*fixture(case)), NONCE, case, -9 if case == 'missing' else 0)
            self.assertFalse(result['metal_verified'])
            self.assertFalse(result['native_reader_dependency_verified'])
            self.assertEqual(result['intentional_host_termination'], case == 'missing')

    def test_rejects_early_or_false_success_release(self):
        for case in ('delayed', 'error', 'producer-error', 'missing'):
            abi, row = fixture(case)
            changes = dict(run='f' * 32, schema=True, initial_status=0, early_pending=0,
                           events=3, positive_fences=99, error_fences=3, last_status=7,
                           stage='timeout-success', metal_verified=True, physical_iphone=True,
                           buffers_retained=not row['buffers_retained'], cleaned=not row['cleaned'])
            for name, value in changes.items():
                with self.subTest(case=case, field=name):
                    changed = copy.deepcopy(row); changed[name] = value
                    with self.assertRaises(ValueError):
                        validate(serial(abi, changed), NONCE, case, -9 if case == 'missing' else 0)

    def test_rejects_missing_response_clean_exit_or_cleanup(self):
        text = serial(*fixture('missing'))
        for tail in ('MPC_LINUX_EXIT=0\n', 'MPC_COMPLETION_EXIT=0\n'):
            with self.assertRaises(ValueError): validate(text + tail, NONCE, 'missing', -9)
        with self.assertRaises(ValueError): validate(text, NONCE, 'missing', 0)

    def test_rejects_duplicate_receipt_and_wrong_exit(self):
        for case in ('delayed', 'error', 'producer-error', 'missing'):
            abi, row = fixture(case); text = serial(abi, row)
            with self.assertRaises(ValueError):
                validate(text + 'MPC_COMPLETION_RESULT ' + json.dumps(row), NONCE, case, -9 if case == 'missing' else 0)
            with self.assertRaises(ValueError): validate(text, NONCE, case, -1)

    def test_missing_control_requires_completed_real_abi(self):
        abi, row = fixture('missing')
        for key in ('signals', 'fork_exec', 'pthread_tls_futex', 'mmap_protection'):
            changed = dict(abi); changed[key] = False
            with self.assertRaises(ValueError): validate(serial(changed, row), NONCE, 'missing', -9)

    def test_failed_producer_must_not_issue_a_third_display_flush(self):
        text = serial(*fixture('producer-error'))
        with self.assertRaises(ValueError):
            validate(text + 'MPC_CONTROL_FLUSH {"index":3,"fence_id":13}\n', NONCE, 'producer-error', 0)
        with self.assertRaises(ValueError):
            validate(text.replace('"fence_id": 12', '"fence_id": 11'), NONCE, 'producer-error', 0)


if __name__ == '__main__':
    unittest.main()
