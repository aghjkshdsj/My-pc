#!/bin/bash
set -euo pipefail
app=build/DerivedData/Build/Products/Release-iphoneos/Madeira.app
xcodebuild -project app/Madeira.xcodeproj -scheme Madeira \
    -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
    -derivedDataPath build/DerivedData \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
    build 2>&1 | tee build/xcodebuild.log
python3 build/linux-arm/embed-runtime.py build/linux-arm/output/guest build/linux-arm/output/ios "$app"
mkdir -p build/ARM-IPA/Payload
ditto "$app" build/ARM-IPA/Payload/Madeira.app
cd build/ARM-IPA
zip -qry SomethingPC-SteamARM64.ipa Payload
unzip -t SomethingPC-SteamARM64.ipa > archive-check.txt
shasum -a 256 SomethingPC-SteamARM64.ipa > SomethingPC-SteamARM64.ipa.sha256
python3 - <<'PY'
import json, plistlib, zipfile
from pathlib import Path
archive = Path('SomethingPC-SteamARM64.ipa')
assert 1_000_000 < archive.stat().st_size < 2_000_000_000, 'IPA outside expected/release asset size limits'
with zipfile.ZipFile(archive) as ipa:
    base = 'Payload/Madeira.app/'
    info = plistlib.loads(ipa.read(base + 'Info.plist'))
    assert ipa.getinfo(base + info['CFBundleExecutable']).file_size > 1_000_000
    assert ipa.getinfo(base + 'Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu').file_size > 1_000_000
    manifest = json.loads(ipa.read(base + 'LinuxRuntime/manifest.json'))
    if base + 'LinuxRuntime/graphics.json' in ipa.namelist():
        for name in ['EGL', 'GLESv2']:
            provider = base + f'Frameworks/{name}.framework/'
            assert ipa.getinfo(provider + name).file_size > 100_000, 'Metal IPA is missing an ANGLE provider'
            assert plistlib.loads(ipa.read(provider + 'Info.plist'))['CFBundleExecutable'] == name
        assert info['SomethingPCBuildCommit'], 'Metal IPA is missing its source commit'
        print('MYPC_IPA_DYNAMIC_ANGLE_PROVIDERS_OK')
    assert manifest['architecture'] == 'aarch64'
    for asset in manifest['files']:
        assert ipa.getinfo(base + 'LinuxRuntime/' + asset['name'] + ('.gz' if asset['gzip'] else '')).file_size > 0
    assert ipa.read(base + 'madeira-jit.js') == Path('../../app/Madeira/madeira-jit.js').read_bytes()
print(f'Verified iPhone IPA with embedded Linux runtime: {archive.stat().st_size:,} bytes')
PY
