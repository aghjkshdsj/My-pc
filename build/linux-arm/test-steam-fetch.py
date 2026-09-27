import importlib.util
import pathlib
import struct
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("steam_fetch", pathlib.Path(__file__).with_name("steam-arm-fetch.py"))
steam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(steam)

class SteamARMTests(unittest.TestCase):
    def test_requires_native_client_and_sha256(self):
        manifest = '"linuxarm64" { "version" "1" "bins_linuxarm64" { "file" "bins_linuxarm64_linuxarm64.zip.' + 'a' * 40 + '" "size" "64" "sha2" "' + 'b' * 64 + '" } }'
        self.assertEqual(steam.parse_manifest(manifest)[0], "1")
        for changed in [manifest.replace("linuxarm64", "win64"), manifest.replace('"sha2"', '"sha"'), manifest.replace('"size" "64"', '"size" "0"'), manifest[:-1]]:
            with self.assertRaises(ValueError):
                steam.parse_manifest(changed)

    def test_rejects_x64_windows_and_truncated_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder, "steam")
            arm = bytearray(64)
            arm[:6] = b"\x7fELF\x02\x01"
            struct.pack_into("<H", arm, 18, 183)
            path.write_bytes(arm)
            steam.verify_arm64(path)
            for value in [b"MZ" + bytes(62), bytes(12), arm[:18] + b"\x3e\x00" + arm[20:]]:
                path.write_bytes(value)
                with self.assertRaises(ValueError):
                    steam.verify_arm64(path)

    def test_zip_cannot_escape_or_overwrite_account_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            destination = root / "staged"
            destination.mkdir()
            archive = root / "package.zip"
            for name in ["../outside", "/outside", "a/../../outside", "a\\..\\..\\outside", "C:outside"]:
                with self.subTest(name=name):
                    entry = zipfile.ZipInfo("placeholder")
                    entry.filename = name  # Preserve malicious backslashes on Windows too.
                    with zipfile.ZipFile(archive, "w") as package:
                        package.writestr(entry, "bad")
                    with self.assertRaises(ValueError):
                        steam.extract(archive, destination)
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("config/loginusers.vdf", "do not install")
                package.writestr("steamapps/game", "do not install")
                package.writestr("steamrtarm64/steam", "ok")
                package.writestr("steamrtarm64\\libs/", "")
            steam.extract(archive, destination)
            self.assertFalse((destination / "config").exists())
            self.assertFalse((destination / "steamapps").exists())
            self.assertEqual((destination / "steamrtarm64/steam").read_text(), "ok")

    def test_internal_links_and_escaping_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            destination = root / "staged"
            destination.mkdir()
            archive = root / "package.zip"
            for value in ["../../outside", "/outside"]:
                entry = zipfile.ZipInfo("libs/link")
                entry.external_attr = 0o120755 << 16
                with zipfile.ZipFile(archive, "w") as package:
                    package.writestr(entry, value)
                with self.assertRaises(ValueError):
                    steam.extract(archive, destination)
            entry = zipfile.ZipInfo("libs/link")
            entry.external_attr = 0o120755 << 16
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("libs/real", "library")
                package.writestr(entry, "real")
            steam.install_links(steam.extract(archive, destination), destination)
            self.assertEqual((destination / "libs/link").read_text(), "library")
            steam.install_links([(destination / "alias", "libs")], destination)
            self.assertEqual((destination / "alias/real").read_text(), "library")
            with self.assertRaises(ValueError):
                steam.install_links([(destination / "libs/loop", "..")], destination)

unittest.main()
