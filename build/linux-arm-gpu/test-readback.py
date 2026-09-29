#!/usr/bin/env python3
import importlib.util
import pathlib
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('gpu_readback', pathlib.Path(__file__).with_name('probe-guest.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadbackTests(unittest.TestCase):
    def test_console_or_incomplete_buffer_cannot_pass_as_gpu_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary, 'frame')
            self.assertIsNone(module.frame_digest(path))
            path.write_bytes(struct.pack('<III', 64, 48, 256) + bytes(64 * 48 * 4))
            self.assertIsNone(module.frame_digest(path))
            path.write_bytes(struct.pack('<III', 4097, 48, 256))
            self.assertIsNone(module.frame_digest(path))
            path.write_bytes(struct.pack('<III', 64, 48, 256) + bytes(500))
            self.assertIsNone(module.frame_digest(path))

    def test_valid_primary_pixels_produce_distinct_frame_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary, 'frame')
            header = struct.pack('<III', 64, 48, 256)
            colors = [bytes([0, 0, 255, 255]), bytes([0, 255, 0, 255]), bytes([255, 0, 0, 255])]
            pixels = b''.join(color * (64 * 16) for color in colors)
            path.write_bytes(header + pixels)
            first = module.frame_digest(path)
            self.assertIsNotNone(first)
            path.write_bytes(header + pixels[4:] + pixels[:4])
            self.assertNotEqual(first, module.frame_digest(path))


if __name__ == '__main__':
    unittest.main()
