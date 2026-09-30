#!/bin/bash
set -euo pipefail
platform="${1:-ios}"
case "$platform" in ios|macos) ;; *) exit 2;; esac
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$repo_root/build/linux-arm-gpu/work-$platform"
pin=7eadb056ae0f91d979059544d0ddcd2d5a40be92
mkdir -p "$work"
git clone --filter=blob:none --no-checkout https://github.com/utmapp/UTM.git "$work/utm"
git -C "$work/utm" checkout --detach "$pin"
test "$(git -C "$work/utm" rev-parse HEAD)" = "$pin"
python3 "$repo_root/build/linux-arm/prepare-utm.py" "$work/utm"
python3 "$repo_root/build/linux-arm-gpu/prepare-gpu.py" "$work/utm"
cd "$work/utm"
NCPU=3 bash scripts/build_dependencies.sh -p "$platform" -a arm64 2>&1 | tee "$work/build.log"
case "$platform" in ios) sysroot=sysroot-iOS-arm64;; macos) sysroot=sysroot-macOS-arm64;; esac
output="$repo_root/build/linux-arm-gpu/output/$platform"
mkdir -p "$output"
ditto "$sysroot/Frameworks" "$output/Frameworks"
ditto "$sysroot/share/qemu" "$output/qemu"
if [ "$platform" = macos ]; then
    clang -std=c11 -Wall -Wextra -Wno-unused-parameter \
        "$repo_root/build/linux-arm/host-launcher.c" "$repo_root/app/Madeira/LinuxVMBridge.c" \
        -Wl,-rpath,@executable_path/Frameworks -o "$output/host-launcher"
    for framework in "$output/Frameworks/"*.framework; do codesign --force --sign - "$framework"; done
    codesign --force --sign - "$output/host-launcher"
fi
tar -czf "$repo_root/build/linux-arm-gpu/output/experimental-gpu-$platform.tar.gz" -C "$output" .
