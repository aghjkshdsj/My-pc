import pathlib
import stat
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from build_guest_gpu_payload import parse_newc
from make_initramfs import record
from stage_guest_runtime import package


class NewcInputTests(unittest.TestCase):
    def archive(self, name='mpc-abi', data=b'ELF', mode=stat.S_IFREG | 0o755):
        return record(name, mode, data) + record('TRAILER!!!', 0, inode=2)

    def test_regular_seed_retained_without_host_extraction(self):
        self.assertEqual(parse_newc(self.archive())['mpc-abi'], (stat.S_IFREG | 0o755, b'ELF', 0, 0))

    def test_path_escape_rejected(self):
        for name in ['/outside', '../outside', 'bin/../../outside']:
            with self.subTest(name=name), self.assertRaises(AssertionError):
                parse_newc(self.archive(name))

    def test_symlink_seed_rejected(self):
        with self.assertRaises(AssertionError):
            parse_newc(self.archive('mpc-abi', b'/outside', stat.S_IFLNK | 0o777))

    def test_duplicate_rejected(self):
        data = record('mpc-abi', stat.S_IFREG | 0o755, b'first')
        with self.assertRaises(AssertionError):
            parse_newc(data + self.archive())

    def test_truncated_inputs_rejected(self):
        data = self.archive()
        for size in [0, 6, 109, 114, len(data) - 10]:
            with self.subTest(size=size), self.assertRaises(AssertionError):
                parse_newc(data[:size])

    def test_missing_trailer_rejected(self):
        with self.assertRaises(AssertionError):
            parse_newc(record('mpc-abi', stat.S_IFREG | 0o755, b'ELF'))

    def test_trailing_hidden_content_rejected(self):
        with self.assertRaises(AssertionError):
            parse_newc(self.archive() + b'hidden')

    def test_loader_diversions_are_not_package_owners(self):
        diversion = SimpleNamespace(returncode=0, stdout='diversion by libc6 from: /lib/ld.so\ndiversion by libc6 to: /usr/lib/ld.so\n')
        owner = SimpleNamespace(returncode=0, stdout='libc6:arm64: /usr/lib/ld.so\n')
        with patch('stage_guest_runtime.subprocess.run', side_effect=[diversion, owner]), \
             patch('stage_guest_runtime.capture', return_value='libc6:arm64\t2.39-1\tglibc\t2.39-1'):
            result = package(pathlib.Path('/lib/ld.so'))
        self.assertEqual(result, {'binary': 'libc6:arm64', 'version': '2.39-1', 'source': 'glibc', 'source_version': '2.39-1'})


if __name__ == '__main__':
    unittest.main()
