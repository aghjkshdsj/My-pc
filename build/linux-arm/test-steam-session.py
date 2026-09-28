#!/usr/bin/env python3
"""Exercise updater restarts and the unmodified helper with a fake Steam tree."""
import hashlib
import os
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent


@unittest.skipUnless(os.name == 'posix' and pathlib.Path('/usr/bin/taskset').exists(), 'Linux taskset required')
class SessionTests(unittest.TestCase):
    def test_update_restart_preserves_vendor_files_and_arguments(self):
        with tempfile.TemporaryDirectory(prefix='steam session ') as folder:
            home = pathlib.Path(folder)
            root = home / '.local/share/Steam'
            native = root / 'steamrtarm64'
            native.mkdir(parents=True)
            (root / 'arm64-verification.json').write_text('{}')
            helper = native / 'steamwebhelper.sh'
            helper.write_text('#!/bin/bash\nexec taskset 0x7c "$(dirname "$0")/steamwebhelper" "$@"\n')
            (native / 'steamwebhelper').write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/received"\n')
            (native / 'steam').write_text('''#!/bin/bash
if [ ! -e "$HOME/updated" ]; then touch "$HOME/updated"; exit 42; fi
exec "$(dirname "$0")/steamwebhelper.sh" "$@"
''')
            for path in native.iterdir():
                path.chmod(0o755)
            digest = hashlib.sha256(helper.read_bytes()).digest()
            result = subprocess.run(['bash', str(HERE / 'steam-session.sh'), 'argument with spaces'],
                                    env=dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share')),
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('status 42', result.stdout)
            self.assertEqual(digest, hashlib.sha256(helper.read_bytes()).digest())
            self.assertIn('argument with spaces', (home / 'received').read_text().splitlines())
            self.assertEqual((home / '.steam/root').resolve(), root)

    def test_other_taskset_requests_are_delegated(self):
        command = ['--pid', str(os.getpid())]
        expected = subprocess.run(['/usr/bin/taskset', *command], capture_output=True, check=True)
        actual = subprocess.run([str(HERE / 'steam-bin/taskset'), *command], capture_output=True, check=True)
        self.assertEqual(actual.stdout, expected.stdout)

    def test_update_restart_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            home = pathlib.Path(folder)
            root = home / '.local/share/Steam'
            native = root / 'steamrtarm64'
            native.mkdir(parents=True)
            (root / 'arm64-verification.json').write_text('{}')
            executable = native / 'steam'
            executable.write_text('#!/bin/sh\nexit 42\n')
            executable.chmod(0o755)
            result = subprocess.run(['bash', str(HERE / 'steam-session.sh')],
                                    env=dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share')),
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.count('status 42'), 5)
            self.assertIn('too many update restarts', result.stdout)


if __name__ == '__main__':
    unittest.main()
