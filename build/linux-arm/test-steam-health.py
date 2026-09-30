import pathlib
import tempfile
import unittest
from steam_health import helper_started, process_health, wait_category


class HealthTests(unittest.TestCase):
    def test_helper_detection_uses_the_process_name_not_arguments(self):
        self.assertTrue(helper_started(' 21 20 steamwebhelper /some/path --type=renderer\n'))
        self.assertFalse(helper_started(' 20 1 bash ./steamwebhelper.sh\n'))
        self.assertFalse(helper_started(' 20 1 steam argument-steamwebhelper\n'))

    def test_snapshot_emits_only_known_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            process = root / '123'
            process.mkdir()
            (process / 'comm').write_text('steam\n')
            (process / 'stat').write_text('123 (steam) ' + ' '.join(['S'] + ['0'] * 10 + ['25', '7']))
            (process / 'status').write_text('VmRSS:\t1234 kB\nThreads:\t4\nSecret:\tDO_NOT_EMIT\n')
            (process / 'wchan').write_text('futex_wait_queue')
            (process / 'cmdline').write_text('DO_NOT_EMIT')
            report = process_health(root)
            self.assertEqual(report['steam'][0], {'state': 'S', 'cpu_ticks': 32,
                             'main_wait': 'futex', 'rss_kib': 1234, 'threads': 4})
            self.assertNotIn('DO_NOT_EMIT', str(report))
            self.assertIsNone(report['entropy_bits'])

    def test_wait_names_are_reduced_to_fixed_labels(self):
        self.assertEqual(wait_category('pipe_read'), 'pipe')
        self.assertEqual(wait_category('wait_for_random_bytes'), 'entropy')
        self.assertEqual(wait_category('SECRET_UNEXPECTED_TEXT'), 'other')


if __name__ == '__main__':
    unittest.main()
