#!/usr/bin/env python3
"""Exercise SDK game launch paths, updater restarts, and vendor file preservation."""
import hashlib
import os
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent


@unittest.skipUnless(os.name == 'posix' and pathlib.Path('/usr/bin/taskset').exists(), 'Linux taskset required')
class SessionTests(unittest.TestCase):
    def make_client(self, home, launcher):
        root = home / '.local/share/Steam'
        native = root / 'steamrtarm64'
        native.mkdir(parents=True)
        (root / 'arm64-verification.json').write_text('{}')
        executable = native / 'steam'
        executable.write_text(launcher)
        executable.chmod(0o755)
        return root

    def run_session(self, home, *arguments):
        return subprocess.run(['bash', str(HERE / 'steam-session.sh'), *arguments],
                              env=dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / '.local/share')),
                              capture_output=True, text=True, timeout=15)

    def test_missing_lsof_fails_before_downloading(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(['/bin/bash', str(HERE / 'steam-session.sh')],
                                    env=dict(os.environ, PATH=folder, HOME=folder),
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('requires lsof', result.stderr)
            self.assertEqual(list(pathlib.Path(folder).iterdir()), [])

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

    def test_game_launch_uses_arm64_sdk_and_preserves_data(self):
        with tempfile.TemporaryDirectory(prefix='steam game launch ') as folder:
            home = pathlib.Path(folder)
            root = self.make_client(home, '''#!/bin/bash
exec "$HOME/.steam/sdkarm64/steam-launch-wrapper" 'game with spaces' "$@"
''')
            sdk = root / 'linuxarm64'
            sdk.mkdir()
            wrapper = sdk / 'steam-launch-wrapper'
            wrapper.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/game-launch"\n')
            wrapper.chmod(0o755)
            overlay = root / 'steamrtarm64/gameoverlayrenderer.so'
            overlay.write_bytes(b'ARM64 overlay fixture')
            vendor_digests = {path: hashlib.sha256(path.read_bytes()).digest() for path in (wrapper, overlay)}
            data_paths = [root / name for name in ('config/loginusers.vdf', 'userdata/1/settings',
                                                   'steamapps/common/example/game-data')]
            for path in data_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'existing account or game data')
            for _ in range(2):
                result = self.run_session(home, 'argument with spaces')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((home / 'game-launch').read_text().splitlines(),
                                 ['game with spaces', 'argument with spaces'])
                for alias, target in (('sdkarm64', sdk), ('steam', root), ('root', root)):
                    self.assertTrue((home / '.steam' / alias).is_symlink())
                    self.assertEqual((home / '.steam' / alias).resolve(), target)
                for alias in ('bin32', 'bin64', 'sdk32', 'sdk64'):
                    self.assertFalse((home / '.steam' / alias).exists())
                    self.assertFalse((home / '.steam' / alias).is_symlink())
                for path, digest in vendor_digests.items():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest)
                for path in data_paths:
                    self.assertEqual(path.read_bytes(), b'existing account or game data')

    def test_stale_links_repaired_and_existing_paths_preserved(self):
        with tempfile.TemporaryDirectory(prefix='steam existing paths ') as folder:
            home = pathlib.Path(folder)
            root = self.make_client(home, '#!/bin/bash\nexit 0\n')
            for directory in ('linuxarm64', 'ubuntu12_32', 'ubuntu12_64', 'linux32', 'linux64'):
                (root / directory).mkdir()
            links = home / '.steam'
            links.mkdir()
            for name in ('root', 'steam', 'sdkarm64', 'sdk32', 'sdk64'):
                (links / name).symlink_to(home / 'old-installation', target_is_directory=True)
            (links / 'bin32').mkdir()
            (links / 'bin32/keep').write_bytes(b'keep real directory')
            (links / 'bin64').write_bytes(b'keep real file')
            for _ in range(2):
                result = self.run_session(home)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for alias, directory in (('root', ''), ('steam', ''), ('sdkarm64', 'linuxarm64'),
                                         ('sdk32', 'linux32'), ('sdk64', 'linux64')):
                    self.assertTrue((links / alias).is_symlink())
                    self.assertEqual((links / alias).resolve(), root / directory)
                self.assertFalse((links / 'bin32').is_symlink())
                self.assertEqual((links / 'bin32/keep').read_bytes(), b'keep real directory')
                self.assertFalse((links / 'bin64').is_symlink())
                self.assertEqual((links / 'bin64').read_bytes(), b'keep real file')
                self.assertFalse((home / 'old-installation').exists())

    def test_x86_aliases_use_the_matching_vendor_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            home = pathlib.Path(folder)
            root = self.make_client(home, '#!/bin/bash\nexit 0\n')
            directories = {'bin32': 'ubuntu12_32', 'bin64': 'ubuntu12_64',
                           'sdk32': 'linux32', 'sdk64': 'linux64'}
            for directory in directories.values():
                (root / directory).mkdir()
            result = self.run_session(home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for alias, directory in directories.items():
                self.assertEqual((home / '.steam' / alias).resolve(), root / directory)
            self.assertFalse((home / '.steam/sdkarm64').is_symlink())

    def test_updater_added_sdk_is_available_on_restart(self):
        with tempfile.TemporaryDirectory(prefix='steam update sdk ') as folder:
            home = pathlib.Path(folder)
            root = self.make_client(home, '''#!/bin/bash
if [ ! -e "$HOME/updated" ]; then
    mkdir "$PWD/linuxarm64"
    cp "$HOME/vendor-wrapper" "$PWD/linuxarm64/steam-launch-wrapper"
    touch "$HOME/updated"
    exit 42
fi
exec "$HOME/.steam/sdkarm64/steam-launch-wrapper" "$@"
''')
            template = home / 'vendor-wrapper'
            template.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$HOME/game-launch"\n')
            template.chmod(0o755)
            result = self.run_session(home, 'argument with spaces')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count('status 42'), 1)
            self.assertEqual((home / '.steam/sdkarm64').resolve(), root / 'linuxarm64')
            self.assertEqual((home / 'game-launch').read_text().splitlines(), ['argument with spaces'])
            self.assertEqual((root / 'linuxarm64/steam-launch-wrapper').read_bytes(), template.read_bytes())

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
