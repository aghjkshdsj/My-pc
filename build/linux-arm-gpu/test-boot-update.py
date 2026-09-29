"""Verify the appended cpio payload stays within reserved startup paths."""
import importlib.util
import pathlib
import stat
import unittest

spec = importlib.util.spec_from_file_location('update', pathlib.Path(__file__).with_name('prepare-boot-update.py'))
update = importlib.util.module_from_spec(spec); spec.loader.exec_module(update)


class InitramfsArchive(unittest.TestCase):
    def test_archive_headers_alignment_and_trailer(self):
        data = update.newc([('scripts/local-bottom/test', stat.S_IFREG | 0o755, b'abc')])
        cursor, records = 0, []
        while cursor < len(data):
            self.assertEqual(data[cursor:cursor + 6], b'070701')
            fields = [int(data[cursor + 6 + i * 8:cursor + 14 + i * 8], 16) for i in range(13)]
            cursor += 110
            name = data[cursor:cursor + fields[11] - 1].decode(); cursor += fields[11]
            cursor = (cursor + 3) // 4 * 4
            body = data[cursor:cursor + fields[6]]; cursor += fields[6]
            cursor = (cursor + 3) // 4 * 4
            records.append((name, body))
        self.assertEqual(records, [('scripts/local-bottom/test', b'abc'), ('TRAILER!!!', b'')])


if __name__ == '__main__':
    unittest.main()
