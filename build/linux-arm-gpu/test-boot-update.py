"""Verify the appended cpio payload stays within reserved startup paths."""
import importlib.util
import hashlib
import os
import pathlib
import shlex
import stat
import subprocess
import tempfile
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


@unittest.skipUnless(os.name == 'posix', 'Actual POSIX ownership, modes and symlinks required')
class InstalledReuse(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='my-pc-boot-reuse-')
        self.addCleanup(self.temporary.cleanup)
        base = pathlib.Path(self.temporary.name)
        self.root, self.payload = base / 'root with spaces', base / 'payload'
        self.root.mkdir(); self.payload.mkdir()
        entries = [
            ('usr/local/bin/my-pc-desktop', 0o755, b'new desktop'),
            ('usr/local/bin/my-pc-steam', 0o755, b'new steam'),
            ('usr/local/lib/my-pc/steam-bin/taskset', 0o755, b'new affinity'),
            ('controller/controller.py', 0o644, b'controller'),
            ('controller/controller-ci.py', 0o644, b'controller observer'),
            ('controller/my-pc-controller.service', 0o644, b'unit'),
            ('controller/70-my-pc-diagnostics.rules', 0o644, b'rule'),
            ('hardware-tests/bench', 0o755, b'diagnostic binary'),
            ('hardware-tests/libfile', 0o644, b'diagnostic library'),
            ('hardware-tests/SHA256SUMS', 0o644, b'fixture checksum table'),
        ]
        files = []
        for name, mode, data in entries:
            source = self.payload / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data); source.chmod(mode)
            files.append(('my-pc-graphics/' + name, stat.S_IFREG | mode, data))
            if name.startswith('usr/'):
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'old reserved launcher'); target.chmod(0o755)
        link = self.payload / 'hardware-tests/libalias'
        link.symlink_to('libfile')
        files.append(('my-pc-graphics/hardware-tests/libalias', stat.S_IFLNK | 0o777, b'libfile'))
        metadata = update.installed_checks(files)
        # Unit fixtures are owned by this unprivileged test account. The real
        # boot payload requires root ownership and is exercised in runtime CI.
        metadata['installed-MODES'] = metadata['installed-MODES'].replace(
            b'0:0:', f'{os.getuid()}:{os.getgid()}:'.encode())
        for name, data in metadata.items():
            (self.payload / name).write_bytes(data)
        checks = entries + [(name, 0o644, data) for name, data in metadata.items()]
        (self.payload / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, _, data in checks))
        self.account = self.root / 'home/steam/.local/share/Steam/config/loginusers.vdf'
        self.account.parent.mkdir(parents=True); self.account.write_bytes(b'account sentinel')
        self.game = self.root / 'home/steam/.local/share/Steam/steamapps/common/game/data'
        self.game.parent.mkdir(parents=True); self.game.write_bytes(b'game sentinel')
        self.operations = base / 'operations'

    def run_hook(self):
        source = pathlib.Path(__file__).with_name('graphics-update.sh').read_text()
        source = source.replace('read -r command_line </proc/cmdline', "command_line='my_pc_graphics=virgl'")
        start, end = source.index('root_command() {'), source.index('\nfail() {')
        source = source[:start] + '''root_command() {
    printf '%s\\n' "$*" >> "$operations"
    if [ "$1" = sync ]; then return 0; fi
    command=$1; shift
    "/usr/bin/$command" "$@"
}
''' + source[end:]
        source = source.replace('/my-pc-graphics', shlex.quote(str(self.payload)))
        source = source.replace('>/dev/console', '').replace('poweroff -f || reboot -f || true', 'true')
        self.operations.write_text('')
        result = subprocess.run(['/bin/sh', '-c', source], capture_output=True, text=True, timeout=10,
                                env=dict(os.environ, rootmnt=str(self.root), operations=str(self.operations)))
        self.assertEqual(self.account.read_bytes(), b'account sentinel')
        self.assertEqual(self.game.read_bytes(), b'game sentinel')
        return result

    def installed(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)

    def test_unchanged_install_reuses_without_copy_chmod_move_or_sync(self):
        self.installed()
        target = self.root / 'usr/local/lib/my-pc/hardware-tests/bench'
        before = target.stat()
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MYPC_GRAPHICS_UPDATE_REUSED=1', result.stdout)
        self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_ctime_ns),
                         (target.stat().st_ino, target.stat().st_mtime_ns, target.stat().st_ctime_ns))
        self.assertFalse(any(line.split()[0] in ('cp', 'chmod', 'mv', 'sync', 'mkdir', 'ln')
                             for line in self.operations.read_text().splitlines()))
        self.assertNotIn('sha256sum -c SHA256SUMS', self.operations.read_text())

    def test_corrupt_bytes_or_executable_mode_require_repair(self):
        self.installed()
        target = self.root / 'usr/local/lib/my-pc/hardware-tests/bench'
        for corrupt in (lambda: target.write_bytes(b'corrupted'), lambda: target.chmod(0o644)):
            corrupt()
            result = self.run_hook()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)
            self.assertEqual(target.read_bytes(), b'diagnostic binary')
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)

    def test_wrong_library_link_or_missing_unit_requires_repair(self):
        self.installed()
        link = self.root / 'usr/local/lib/my-pc/hardware-tests/libalias'
        link.unlink(); link.symlink_to('bench')
        unit = self.root / 'etc/systemd/system/my-pc-controller.service'
        unit.unlink()
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)
        self.assertEqual(link.readlink().as_posix(), 'libfile')
        self.assertEqual(unit.read_bytes(), b'unit')

    def test_existing_startup_symlink_is_refused_even_with_identical_bytes(self):
        self.installed()
        target = self.root / 'usr/local/bin/my-pc-steam'
        alias = self.root / 'usr/local/bin/alias'; alias.write_bytes(target.read_bytes())
        target.unlink(); target.symlink_to('alias')
        result = self.run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)

    def test_unverified_metadata_never_reuses(self):
        self.installed()
        (self.payload / 'installed-SHA256SUMS').write_text('tampered metadata')
        result = self.run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)

    def test_unused_source_bytes_are_not_needed_for_matching_install(self):
        self.installed()
        (self.payload / 'hardware-tests/bench').write_bytes(b'damaged unused source')
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MYPC_GRAPHICS_UPDATE_REUSED=1', result.stdout)
        self.assertEqual((self.root / 'usr/local/lib/my-pc/hardware-tests/bench').read_bytes(),
                         b'diagnostic binary')

    def test_damaged_source_is_refused_before_any_repair_write(self):
        self.installed()
        (self.payload / 'hardware-tests/bench').write_bytes(b'damaged repair source')
        target = self.root / 'usr/local/lib/my-pc/hardware-tests/bench'
        target.write_bytes(b'damaged installed file')
        before = target.stat()
        result = self.run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('MYPC_GRAPHICS_UPDATE_REUSED', result.stdout)
        self.assertEqual(target.read_bytes(), b'damaged installed file')
        self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_ctime_ns),
                         (target.stat().st_ino, target.stat().st_mtime_ns, target.stat().st_ctime_ns))
        self.assertFalse(any(line.split()[0] in ('cp', 'chmod', 'mv', 'mkdir', 'ln')
                             for line in self.operations.read_text().splitlines()))


if __name__ == '__main__':
    unittest.main()
