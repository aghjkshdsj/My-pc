"""Exercise the actual Foundation desktop installer policy and ZIP reader."""
from pathlib import Path
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile

driver = Path(__file__).resolve().parent
app = driver / 'runtime/app/Madeira'
compiler = os.environ.get('SWIFTC') or shutil.which('swiftc')
if not compiler: raise SystemExit('swiftc is required')
with tempfile.TemporaryDirectory(prefix='mypc-desktop-tests-') as directory:
    root = Path(directory)
    runtime = root / 'SteamRuntime.swift'
    # Keep the actual pure policy/ZIP reader; the actor calls guest entry points
    # which cannot be exercised by a host test. Never modify packaged sources.
    runtime.write_text((app / 'SteamRuntime.swift').read_text().replace('#if canImport(CryptoKit)', '#if false'))
    modules = root / 'modules'; modules.mkdir()
    (modules / 'module.modulemap').write_text('module zlib [system] { header "/usr/include/zlib.h" link "z" export * }\n')
    fixture = root / 'fixtures'; fixture.mkdir()
    for name, entries in {
        'valid.zip': [('bin/cef/cef.win64/libcef.dll', b'fixture')],
        'traversal.zip': [('../escape.dll', b'bad')],
        'collision.zip': [('a.dll', b'a'), ('A.dll', b'b')],
        # Above the pinned helper's 64 MB per-file limit, below desktop's limit.
        'large.zip': [('large.dll', bytes(65 * 1024 * 1024))],
    }.items():
        with zipfile.ZipFile(fixture / name, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, data in entries: archive.writestr(path, data)
    with zipfile.ZipFile(fixture / 'link.zip', 'w') as archive:
        info = zipfile.ZipInfo('link.dll'); info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, '../outside')
    bad = bytearray((fixture / 'valid.zip').read_bytes())
    central = bad.index(b'PK\x01\x02'); bad[central + 16] ^= 1
    (fixture / 'crc.zip').write_bytes(bad)
    source = driver / 'tests/steam_desktop.swift'
    binary = root / 'check-desktop'
    subprocess.run([compiler, '-O', '-parse-as-library', '-I', str(modules), str(app / 'SteamKeyValues.swift'),
                    str(app / 'SteamInstall.swift'), str(runtime), str(app / 'NativeSteamDesktop.swift'),
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), str(driver / 'tests/steam-desktop-manifest.txt'), str(fixture)], check=True)
