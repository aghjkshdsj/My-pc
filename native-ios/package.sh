#!/bin/bash
set -euo pipefail
driver="$(cd "$(dirname "$0")" && pwd)"
runtime="$driver/runtime"
cd "$runtime"
test -s app/Madeira/arm64ec-windows/dockhost.exe
test -s app/Madeira/arm64ec-windows/dock-notices.txt
test -s app/Madeira/x86_64-vcruntime/msvcp140.dll
bash build/stage-licenses.sh
# Keep Debug's C/Objective-C host flags: the reference reports guest crashes
# with a fully Release host. Optimize Swift account/library/download work;
# the same optimization is exercised by the protocol tests under ASan.
# FEX, Wine and DXMT libraries are separately optimized source builds.
xcodebuild -project app/Madeira.xcodeproj -scheme Madeira -configuration Debug \
  -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build/MyPCNative \
  SWIFT_OPTIMIZATION_LEVEL=-O SWIFT_COMPILATION_MODE=wholemodule \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  DEVELOPMENT_TEAM="" build 2>&1 | tee "$driver/out/xcodebuild.log"
app=build/MyPCNative/Build/Products/Debug-iphoneos/Madeira.app
test -d "$app"
plutil -lint "$app/Info.plist"
executable=$(/usr/libexec/PlistBuddy -c 'Print CFBundleExecutable' "$app/Info.plist")
xcrun lipo "$app/$executable" -verify_arch arm64
xcrun vtool -show-build "$app/$executable" | grep -q 'platform IOS'
if find "$app" -iname '*qemu*' -o -iname '*virgl*' -o -name rootfs.raw | grep -q .; then
  echo 'Unexpected VM runtime in native app' >&2; exit 1
fi
mkdir -p "$driver/out/IPA/Payload"
ditto "$app" "$driver/out/IPA/Payload/Madeira.app"
(
  cd "$driver/out/IPA"
  zip -qry MyPC-NativeSteam.ipa Payload
  unzip -t MyPC-NativeSteam.ipa > archive-verification.txt
  shasum -a 256 MyPC-NativeSteam.ipa > MyPC-NativeSteam.ipa.sha256
)
python3 "$driver/verify-ipa.py" "$driver/out/IPA/MyPC-NativeSteam.ipa" "$driver/source-lock.json"

# Corresponding source includes the actual runtime forks and overlays. Leave
# build outputs/toolchains out; recipes and the lock reproduce those inputs.
python3 - "$runtime" "$driver" <<'PY'
from pathlib import Path
import json, subprocess, sys, tarfile, hashlib
runtime, driver = map(Path, sys.argv[1:])
paths = []
for repository in [runtime] + [p.parent for p in runtime.rglob('.git') if p.parent != runtime]:
    if not (repository / '.git').exists(): continue
    for item in subprocess.check_output(['git', '-C', str(repository), 'ls-files', '-z']).decode().split('\0'):
        if item and (repository / item).is_file(): paths.append(repository / item)
paths.extend([runtime / '.mypc-native-overlay.json'])
archive = driver / 'out/MyPC-NativeSteam-Sources.tar.gz'
with tarfile.open(archive, 'w:gz') as output:
    for path in sorted(set(paths)):
        output.add(path, arcname='runtime/' + path.relative_to(runtime).as_posix(), recursive=False)
    for path in driver.iterdir():
        if path.is_file(): output.add(path, arcname='driver/' + path.name, recursive=False)
    workflow = driver.parent / '.github/workflows/native-ios-steam.yml'
    output.add(workflow, arcname='driver/native-ios-steam.yml', recursive=False)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(archive.suffix + '.sha256').write_text(digest + '  ' + archive.name + '\n')
print('Corresponding source:', archive.stat().st_size, 'bytes', digest)
PY
