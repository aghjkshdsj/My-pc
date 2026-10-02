"""Synthetic format tests; fixtures never establish physical device execution."""
import pathlib
import struct
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from verify_ipa import macho_text


class MachOTextTests(unittest.TestCase):
    def fixture(self):
        section = struct.pack('<16s16sQQ8I', b'__text', b'__TEXT', 256, 16, 256, 4, 0, 0, 0x80000400, 0, 0, 0)
        segment = struct.pack('<II16sQQQQiiII', 0x19, 152, b'__TEXT', 0, 4096, 0, 512, 5, 5, 1, 0) + section
        build = struct.pack('<6I', 0x32, 24, 2, 26 << 16, 26 << 16, 0)
        signature = struct.pack('<4I', 0x1d, 16, 512, 32)
        commands = segment + build + signature
        header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 6, 3, len(commands), 0, 0)
        binary = bytearray(header + commands)
        binary += bytes(256 - len(binary)) + bytes(range(16))
        binary += bytes(544 - len(binary))
        return binary

    def test_signature_and_segment_metadata_changes_preserve_code_identity(self):
        original = self.fixture(); changed = bytearray(original)
        struct.pack_into('<Q', changed, 64, 8192)  # signing may alter segment sizes
        struct.pack_into('<I', changed, 220, 64)  # code signature blob size
        changed[512:] = b's' * 64
        self.assertEqual(macho_text(original), macho_text(changed))
        self.assertNotEqual(original, changed)

    def test_modified_executable_bytes_change_identity(self):
        original = self.fixture(); changed = bytearray(original); changed[256] ^= 1
        self.assertNotEqual(macho_text(original), macho_text(changed))

    def test_wrong_platform_or_architecture_rejected(self):
        for offset, value in [(4, 0x1000007), (192, 1)]:
            changed = self.fixture(); struct.pack_into('<I', changed, offset, value)
            with self.assertRaises(AssertionError): macho_text(changed)

    def test_out_of_file_section_rejected(self):
        changed = self.fixture(); struct.pack_into('<Q', changed, 144, 65536)
        with self.assertRaises(AssertionError): macho_text(changed)
