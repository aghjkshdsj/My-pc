"""Raw initramfs extension controls, never phone GPU acceptance."""
import pathlib
import stat
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from build_guest_image_payload import extend_newc
from make_initramfs import record


class GuestImagePayloadTests(unittest.TestCase):
    def test_preserves_raw_records_and_symlinks_without_extracting(self):
        link = record('lib/loader', stat.S_IFLNK | 0o777, b'../usr/lib/loader', inode=2)
        data = record('init', stat.S_IFREG | 0o755, b'old', inode=1) + link + record('TRAILER!!!', 0, inode=3)
        result = extend_newc(data, {'init': (stat.S_IFREG | 0o755, b'new'),
                                    'vk-image-gate': (stat.S_IFREG | 0o755, b'ELF')})
        self.assertIn(link, result)
        self.assertIn(b'new', result)
        self.assertIn(b'vk-image-gate', result)
        self.assertNotIn(b'old', result)

    def test_adds_only_the_two_explicit_diagnostic_binaries(self):
        end = record('TRAILER!!!', 0)
        result = extend_newc(end, {'vk-image-gate': (stat.S_IFREG | 0o755, b'VK-ELF'),
                                   'kms-format-control': (stat.S_IFREG | 0o755, b'KMS-ELF')})
        self.assertIn(b'vk-image-gate', result)
        self.assertIn(b'kms-format-control', result)
        for name in ('../kms-format-control', '/kms-format-control', 'user-data'):
            with self.assertRaises(AssertionError):
                extend_newc(end, {name: (stat.S_IFREG | 0o755, b'ELF')})

    def test_rejects_truncation_duplicate_traversal_and_trailing_content(self):
        entry = record('init', stat.S_IFREG | 0o755, b'old')
        end = record('TRAILER!!!', 0)
        for data in [entry[:-1], entry + entry + end,
                     record('../init', stat.S_IFREG | 0o755, b'old') + end,
                     entry + end + b'bad']:
            with self.assertRaises((AssertionError, ValueError)):
                extend_newc(data, {'init': (stat.S_IFREG | 0o755, b'new')})

    def test_frame_binary_requires_explicit_bounded_addition(self):
        end = record('TRAILER!!!', 0)
        update = {'vk-frames-gate': (stat.S_IFREG | 0o755, b'FRAME-ELF')}
        with self.assertRaises(AssertionError):
            extend_newc(end, update)
        self.assertIn(b'vk-frames-gate', extend_newc(end, update, additions=('vk-frames-gate',)))
        for name in ('../vk-frames-gate', '/vk-frames-gate', 'user-data'):
            with self.assertRaises(AssertionError):
                extend_newc(end, {name: (stat.S_IFREG | 0o755, b'ELF')}, additions=(name,))

    def test_rejects_replacing_symlink_or_adding_unexpected_name(self):
        end = record('TRAILER!!!', 0)
        with self.assertRaises(AssertionError):
            extend_newc(record('init', stat.S_IFLNK | 0o777, b'user-data') + end,
                        {'init': (stat.S_IFREG | 0o755, b'new')})
        with self.assertRaises(AssertionError):
            extend_newc(end, {'user-data': (stat.S_IFREG | 0o755, b'new')})


if __name__ == '__main__':
    unittest.main()
