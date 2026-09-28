#!/usr/bin/env python3
"""Prevent false startup failures and hidden/updater-window false positives."""
import unittest
from steam_window import client_window
from steam_cdp import ready_login, login_target


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
        for url in ['https://steamloopback.host/index.html',
                    'about:blank?createflags=4098&pid=0&browser=-1&useragent=Valve%20Steam%20Client']:
            self.assertTrue(ready_login({'url': url, 'title': 'Sign in to Steam',
                                        'readyState': 'complete', 'passwordVisible': True}))

    def test_only_local_steam_targets_are_inspected(self):
        for target in [{'type': 'page', 'url': 'https://example.com', 'title': 'Sign in to Steam'},
                       {'type': 'page', 'url': 'about:blank', 'title': 'Unrelated popup'},
                       {'type': 'worker', 'url': 'https://steamloopback.host/index.html'}]:
            self.assertFalse(login_target(target))

    def test_loading_blank_or_unrelated_page_is_not_ready(self):
        base = {'url': 'about:blank?createflags=4098', 'title': 'Sign in to Steam',
                'readyState': 'complete', 'passwordVisible': True}
        for state in [None, {}, dict(base, url='https://example.com'), dict(base, readyState='loading'),
                      dict(base, passwordVisible=False), dict(base, title='SharedJSContext')]:
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
