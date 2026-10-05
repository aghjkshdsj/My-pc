"""Synthetic receipt rejection controls; actual ARM boots are a separate workflow."""
import copy
import json
import pathlib
import stat
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_kms_atomic_gate import validate
from build_guest_image_payload import extend_newc
from make_initramfs import record

NONCE = '0123456789abcdef' * 2


def fixture(present=True, input_fence=True, output_fence=True):
    base = dict(schema=1, run=NONCE)
    abi = dict(**base, failures=0, machine='aarch64', elf_arch='aarch64', page_bytes=4096,
               signals=True, mmap_protection=True, pthread_tls_futex=True, fork_exec=True,
               checksum='1d250c45a7bbc87e', wall_ms=1, cpu_ms=1)
    rows = [('MPC_LINUX_ABI ', abi)]
    if present:
        rows.append(('MPC_KMS_CAPS ', dict(**base, connector=31, crtc=34, plane=32,
                     width=1280, height=720, format='XRGB8888', in_fence_fd=input_fence,
                     out_fence_ptr=output_fence, native_reader_dependency_verified=False)))
        for i in range(1, 7):
            rows.append(('MPC_KMS_FLIP ', dict(**base, index=i, slot=i % 3, crtc=34,
                         event_sequence=0, event_sec=0, event_usec=0,
                         out_fence_signaled=output_fence, native_display_timestamp=False,
                         metal_completion_verified=False)))
    rows.append(('MPC_KMS_RESULT ', dict(**base, stage='complete' if present else 'open-drm',
                 exit_code=0 if present else 1, errno=0 if present else 2, buffers=3 if present else 0,
                 flips=6 if present else 0, signaled_out_fences=6 if present and output_fence else 0,
                 invalid_geometry_rejected=present, invalid_input_fence_rejected=present and input_fence,
                 invalid_geometry_errno=34 if present else 0,
                 invalid_input_fence_errno=9 if present and input_fence else 0,
                 cleaned=True, cpu_dumb_control=True, native_reader_dependency_verified=False,
                 metal_verified=False, desktop_verified=False, game_fps_verified=False)))
    return rows


def serial(rows, present=True):
    return '\n'.join(prefix + json.dumps(row) for prefix, row in rows) + '\nMPC_KMS_EXIT=' + (
        '0' if present else '1') + '\nMPC_LINUX_EXIT=0\n'


class AtomicReceiptTests(unittest.TestCase):
    def test_atomic_binary_requires_explicit_safe_addition(self):
        end = record('TRAILER!!!', 0)
        update = {'kms-atomic-gate': (stat.S_IFREG | 0o755, b'ARM-ELF')}
        with self.assertRaises(AssertionError): extend_newc(end, update)
        self.assertIn(b'kms-atomic-gate', extend_newc(end, update, additions=('kms-atomic-gate',)))
        for name in ('../kms-atomic-gate', '/kms-atomic-gate', 'user-data'):
            with self.assertRaises(AssertionError):
                extend_newc(end, {name: (stat.S_IFREG | 0o755, b'ELF')}, additions=(name,))
    def test_all_observed_fence_property_combinations_keep_native_verdict_false(self):
        for input_fence in (False, True):
            for output_fence in (False, True):
                with self.subTest(input_fence=input_fence, output_fence=output_fence):
                    result = validate(serial(fixture(input_fence=input_fence, output_fence=output_fence)), NONCE, True)
                    self.assertFalse(result['native_reader_dependency_verified'])
                    self.assertFalse(result['metal_verified'])
                    self.assertFalse(result['phone_verified'])
    def test_missing_device_is_an_observed_rejection(self):
        result = validate(serial(fixture(False), False), NONCE, False)
        self.assertIsNone(result['capabilities'])
    def test_event_session_identity_and_work_corruption_reject(self):
        changes = [('run', 'f' * 32), ('index', 1), ('slot', 0), ('crtc', 32),
                   ('event_usec', 1000000), ('event_sec', -1), ('event_sequence', True),
                   ('out_fence_signaled', False), ('native_display_timestamp', True),
                   ('metal_completion_verified', True)]
        for key, value in changes:
            rows = fixture(); rows[3][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(serial(rows), NONCE, True)
    def test_unearned_product_and_cleanup_claims_reject(self):
        for key, value in [('metal_verified', True), ('desktop_verified', True), ('game_fps_verified', True),
                           ('native_reader_dependency_verified', True), ('cpu_dumb_control', False),
                           ('cleaned', False), ('flips', 5), ('buffers', 8), ('signaled_out_fences', 5),
                           ('invalid_geometry_rejected', False), ('invalid_geometry_errno', 12),
                           ('invalid_input_fence_errno', 12), ('exit_code', 1)]:
            rows = fixture(); rows[-1][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(serial(rows), NONCE, True)
    def test_duplicate_missing_reordered_or_foreign_receipts_reject(self):
        original = fixture()
        alternatives = [original + [original[-1]], original[:3] + original[4:],
                        original[:2] + [original[3], original[2]] + original[4:],
                        original + [original[2]], original[1:]]
        for rows in alternatives:
            with self.subTest(rows=len(rows)), self.assertRaises((ValueError, AssertionError)):
                validate(serial(rows), NONCE, True)
        with self.assertRaises(ValueError): validate(serial(original).replace('MPC_KMS_EXIT=0', 'MPC_KMS_EXIT=1'), NONCE, True)
        with self.assertRaises(ValueError): validate(serial(original) + 'MPC_KMS_EXIT=0\n', NONCE, True)
    def test_properties_are_not_native_reader_proof(self):
        for key, value in [('native_reader_dependency_verified', True), ('plane', 34),
                           ('out_fence_ptr', 1), ('in_fence_fd', 'true'), ('width', 1920),
                           ('format', 'ARGB8888'), ('schema', True)]:
            rows = fixture(); rows[1][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(serial(rows), NONCE, True)
    def test_missing_device_cannot_claim_partially_completed_flips(self):
        for key, value in [('flips', 1), ('buffers', 1), ('stage', 'complete'), ('errno', 0),
                           ('invalid_geometry_rejected', True), ('cleaned', False)]:
            rows = fixture(False); rows[-1][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(serial(rows, False), NONCE, False)
    def test_invalid_or_wrong_session_reject(self):
        for nonce in ('', 'A' * 32, 'f' * 32, 123):
            with self.subTest(nonce=nonce), self.assertRaises((ValueError, AssertionError)):
                validate(serial(fixture()), nonce, True)


if __name__ == '__main__': unittest.main()
