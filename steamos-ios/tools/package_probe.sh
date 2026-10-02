#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$root/out/xcode"
output="$root/out/package"
mkdir -p "$output/Payload"
test ! -e "$output/Payload/MyPCSteamOSProbe.app"
cp -R "$build/Build/Products/Release-iphoneos/MyPCSteamOSProbe.app" "$output/Payload/"
(cd "$output" && /usr/bin/zip -qr MyPCSteamOS-Probe.ipa Payload)
python3 "$root/tools/verify_ipa.py" "$output/MyPCSteamOS-Probe.ipa" "$GITHUB_SHA" --receipt "$output/verification.json"
(cd "$output" && shasum -a 256 MyPCSteamOS-Probe.ipa > SHA256SUMS)
