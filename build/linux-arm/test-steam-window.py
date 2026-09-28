#!/usr/bin/env python3
"""Prevent false startup failures and hidden/updater-window false positives."""
import unittest
from steam_window import client_window


RENDERER = '/home/steam/.local/share/Steam/steamrtarm64/steamwebhelper --type=renderer --lang=en-US'
VIEWABLE = '  Width: 700\n  Height: 440\n  Map State: IsViewable\n'


class WindowTests(unittest.TestCase):
    def test_arm_login_title_from_cef_log(self):
        result = client_window('  0x200001 "Sign in to": () 700x440+0+0', RENDERER, lambda _: VIEWABLE)
        self.assertEqual(result['title'], 'Sign in to')

    def test_other_full_client_titles(self):
        for title in ['Steam', 'Sign in to Steam', 'Steam Sign In']:
            with self.subTest(title=title):
                self.assertIsNotNone(client_window(f'  0x200001 "{title}": ()', RENDERER, lambda _: VIEWABLE))

    def test_renderer_required(self):
        for process in ['', '/path/steamwebhelper --type=gpu-process', 'echo steamwebhelper --type=renderer']:
            with self.subTest(process=process):
                self.assertIsNone(client_window('0x20 "Steam": ()', process, lambda _: VIEWABLE))

    def test_hidden_tiny_or_disappeared_window_rejected(self):
        for details in ['', VIEWABLE.replace('IsViewable', 'IsUnMapped'), VIEWABLE.replace('700', '1')]:
            with self.subTest(details=details):
                self.assertIsNone(client_window('0x20 "Steam": ()', RENDERER, lambda _: details))

    def test_updater_or_title_substring_rejected(self):
        for title in ['Steam - Updating', 'Downloading Steam', 'Some Steam window', 'Steam.exe']:
            with self.subTest(title=title):
                self.assertIsNone(client_window(f'0x20 "{title}": ()', RENDERER, lambda _: VIEWABLE))


if __name__ == '__main__':
    unittest.main()
