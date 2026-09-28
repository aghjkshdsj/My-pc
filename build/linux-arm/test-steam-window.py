#!/usr/bin/env python3
"""Prevent false startup failures and hidden/updater-window false positives."""
import unittest
from steam_window import client_window
from steam_cdp import ready_login


RENDERER = True
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
        self.assertIsNone(client_window('0x20 "Steam": ()', False, lambda _: VIEWABLE))

    def test_loaded_login_page_is_ready(self):
        self.assertTrue(ready_login({'hostname': 'steamloopback.host', 'readyState': 'complete', 'passwordVisible': True}))

    def test_loading_blank_or_unrelated_page_is_not_ready(self):
        for state in [None, {}, {'hostname': 'example.com', 'readyState': 'complete', 'passwordVisible': True},
                      {'hostname': 'steamloopback.host', 'readyState': 'loading', 'passwordVisible': True},
                      {'hostname': 'steamloopback.host', 'readyState': 'complete', 'passwordVisible': False}]:
            with self.subTest(state=state):
                self.assertFalse(ready_login(state))

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
