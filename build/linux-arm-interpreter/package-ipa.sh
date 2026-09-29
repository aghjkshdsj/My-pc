#!/bin/bash
set -euo pipefail
output=build/linux-arm-interpreter/output
app=build/InterpreterDerivedData/Build/Products/Release-iphoneos/MyPCInterpreter.app
xcodegen generate --spec app/Interpreter/project.yml
xcodebuild -project app/Interpreter/MyPCInterpreter.xcodeproj -scheme MyPCInterpreter \
    -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
    -derivedDataPath build/InterpreterDerivedData \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
    build 2>&1 | tee "$output/xcodebuild.log"
# Verify provenance against the runtime before removing its ad-hoc signature.
python3 - "$output/ios" <<'PY'
import hashlib, json, pathlib, sys
runtime = pathlib.Path(sys.argv[1])
manifest = json.loads((runtime / 'runtime-backend.json').read_text())
binary = runtime / 'Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu'
assert manifest['backend'] == 'tcti' and manifest['requiresJIT'] is False
assert hashlib.sha256(binary.read_bytes()).hexdigest() == manifest['binarySHA256']
PY
python3 build/linux-arm/embed-runtime.py "$output/guest" "$output/ios" "$app"
cp "$output/ios/runtime-backend.json" "$app/runtime-backend.json"
cat > "$app/LinuxRuntime/README.txt" <<'NOTES'
My-pc Linux interpreter development preview. QEMU 10.0.12-utm TCTI.
Precompiled ARM64 dispatch; no host JIT or debugger required.
Two virtual CPUs, 2048 MiB guest RAM and software rendering.
Guest JIT instructions are interpreted and never executed as host code.
No Steam login, downloads, gaming performance or App Store approval is implied.
The source, pins and build instructions accompany this development artifact.
Steam downloads separately from Valve. No Valve binaries are bundled.
NOTES
python3 build/linux-arm-interpreter/audit-app.py "$app"
mkdir -p "$output/IPA/Payload"
ditto "$app" "$output/IPA/Payload/MyPCInterpreter.app"
(cd "$output/IPA" && zip -qry MyPC-SteamARM64-NoJIT.ipa Payload && unzip -t MyPC-SteamARM64-NoJIT.ipa > archive-check.txt && shasum -a 256 MyPC-SteamARM64-NoJIT.ipa > MyPC-SteamARM64-NoJIT.ipa.sha256)
