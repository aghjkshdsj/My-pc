"""Recognize a mapped full-client window, including Valve's ARM login title."""
import re
import subprocess


CLIENT_TITLES = {'Steam', 'Sign in to', 'Sign in to Steam', 'Steam Sign In'}


def inspect_window(window_id):
    result = subprocess.run(['xwininfo', '-id', window_id], capture_output=True,
                            text=True, timeout=5)
    # A window can disappear between the tree snapshot and this query.
    return result.stdout if result.returncode == 0 else ''


def client_window(windows, renderer_ready, inspect=inspect_window):
    # CEF's forked renderer can retain --type=zygote in /proc/cmdline.
    # Readiness comes from a live response from the login page instead.
    if not renderer_ready:
        return None
    for line in windows.splitlines():
        match = re.match(r'\s*(0x[0-9a-fA-F]+)\s+"([^"]*)"', line)
        if not match or match[2] not in CLIENT_TITLES:
            continue
        details = inspect(match[1])
        width = re.search(r'^\s*Width:\s*(\d+)\s*$', details, re.MULTILINE)
        height = re.search(r'^\s*Height:\s*(\d+)\s*$', details, re.MULTILINE)
        if (re.search(r'^\s*Map State:\s*IsViewable\s*$', details, re.MULTILINE)
                and width and height and int(width[1]) >= 300 and int(height[1]) >= 200):
            return {'id': match[1], 'title': match[2], 'details': details}
    return None
