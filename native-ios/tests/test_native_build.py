from pathlib import Path
import importlib.util
import json
import os
import plistlib
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load('native_prepare', ROOT / 'prepare.py')
verifier = load('native_verify', ROOT / 'verify-ipa.py')


class NativeBuildTests(unittest.TestCase):
    def test_runtime_revisions_are_full_commits_and_toolchain_digest_is_sha256(self):
        lock = json.loads((ROOT / 'source-lock.json').read_text())
        for value in [lock['source']['commit'], lock['llvm_commit'], *lock['submodules'].values()]:
            self.assertRegex(value, '^[0-9a-f]{40}$')
        self.assertRegex(lock['llvm_mingw']['sha256'], '^[0-9a-f]{64}$')

    def test_changed_marker_fails_before_modifying_source(self):
        with self.assertRaises(ValueError):
            prepare.replace_once('marker\nmarker', 'marker', 'replacement', 'fixture')

    def test_wrong_checkout_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = list(root.iterdir())
            with self.assertRaisesRegex(ValueError, 'Only native-ios/runtime'):
                prepare.prepare(root)
            self.assertEqual(list(root.iterdir()), before)

    def test_overlay_rebuilds_every_server_object_and_can_be_reapplied(self):
        with tempfile.TemporaryDirectory() as folder:
            driver = Path(folder)
            runtime = driver / 'runtime'
            app = runtime / 'app/Madeira'
            server_path = runtime / 'build/wineserver/build.sh'
            project_path = runtime / 'app/Madeira.xcodeproj/project.pbxproj'
            app.mkdir(parents=True)
            server_path.parent.mkdir(parents=True)
            project_path.parent.mkdir(parents=True)
            (driver / 'NativeApp.swift').write_text('native app fixture')
            (app / 'Library.swift').write_text('            onboarding.presentIfNeeded()\n')
            server_path.write_text('''# Copy the base library if we don't have one yet
unavailable base archive
CC_FLAGS=()
PATCHED_FILES=()
case "${1:-all}" in
old partial rebuild
echo "=== Renaming colliding symbols in every .o (objcopy sweep) ==="
keep rename pass
''')
            project_path.write_text('com.willfaust.madeora\ncom.willfaust.madeora\nIPHONEOS_DEPLOYMENT_TARGET = 17.0;\n')
            (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleDisplayName': 'Madeira'}))

            def fake_git(directory, *args):
                if directory == runtime: return prepare.LOCK['source']['commit']
                return prepare.LOCK['submodules'][directory.name]

            with patch.object(prepare, 'DRIVER', driver), patch.object(prepare, 'git', fake_git), patch.dict(os.environ, {'GITHUB_SHA': '1' * 40, 'GITHUB_RUN_NUMBER': '7'}):
                prepare.prepare(runtime)
                rewritten = server_path.read_text()
                self.assertIn('"$WINE_SRC"/server/*.c', rewritten)
                self.assertIn('keep rename pass', rewritten)
                self.assertNotIn('unavailable base archive', rewritten)
                first = (app / 'Library.swift').read_text()
                prepare.prepare(runtime)
                self.assertEqual((app / 'Library.swift').read_text(), first)
                info = plistlib.loads((app / 'Info.plist').read_bytes())
                self.assertEqual(info['CFBundleVersion'], '3000007')
                self.assertEqual(info['SomethingPCBuildCommit'], '1' * 40)

    def fixture_ipa(self, path, extra=None, machine=0x0100000c):
        lock = json.loads((ROOT / 'source-lock.json').read_text())
        info = {
            'CFBundleIdentifier': lock['bundle_id'], 'CFBundleDisplayName': lock['display_name'],
            'CFBundleExecutable': 'Madeira', 'CFBundleVersion': '3000001',
            'SomethingPCBuildCommit': '1' * 40, 'MyPCNativeSourceCommit': lock['source']['commit'],
            'MyPCNativeBackend': 'native-ios-fex-wine-metal'
        }
        binary = bytearray(1_000_001)
        struct.pack_into('<II', binary, 0, 0xfeedfacf, machine)
        helper = bytearray(100)
        struct.pack_into('<I', helper, 0x3c, 64)
        helper[64:68] = b'PE\0\0'
        struct.pack_into('<H', helper, 68, 0x8664)
        prefix = 'Payload/Madeira.app/'
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(prefix + 'Info.plist', plistlib.dumps(info))
            archive.writestr(prefix + 'Madeira', binary)
            archive.writestr(prefix + 'arm64ec-windows/dockhost.exe', helper)
            for item in ('arm64ec-windows/dock-notices.txt', 'aarch64-windows/fixture.dll',
                         'i386-windows/fixture.dll', 'x86_64-vcruntime/fixture.dll',
                         'licenses/LICENSE-MADEIRA-GPL-3.0.txt', 'licenses/LICENSE-MADEIRA-EXCEPTION.txt'):
                archive.writestr(prefix + item, b'fixture')
            if extra: archive.writestr(prefix + extra, b'fixture')

    def test_package_verifier_checks_identity_runtime_and_native_architecture(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'GITHUB_SHA': '1' * 40}):
            path = Path(folder) / 'fixture.ipa'
            self.fixture_ipa(path)
            result = verifier.verify(path, ROOT / 'source-lock.json')
            self.assertFalse(result['vm_payload'])
            self.fixture_ipa(path, machine=0x01000007)
            with self.assertRaisesRegex(AssertionError, 'ARM64 host'):
                verifier.verify(path, ROOT / 'source-lock.json')

    def test_package_verifier_rejects_vm_payload(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'GITHUB_SHA': '1' * 40}):
            path = Path(folder) / 'fixture.ipa'
            self.fixture_ipa(path, extra='LinuxRuntime/rootfs.raw')
            with self.assertRaisesRegex(AssertionError, 'VM payload'):
                verifier.verify(path, ROOT / 'source-lock.json')


if __name__ == '__main__':
    unittest.main()
