#!/bin/bash
set -euo pipefail
platform="${1:-ios}"
case "$platform" in ios|macos) ;; *) exit 2;; esac
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$repo_root/build/linux-arm-interpreter/work-$platform"
output="$repo_root/build/linux-arm-interpreter/output/$platform"
utm_commit=7eadb056ae0f91d979059544d0ddcd2d5a40be92
mkdir -p "$work"
if [ ! -d "$work/utm/.git" ]; then
    git clone --filter=blob:none --no-checkout https://github.com/utmapp/UTM.git "$work/utm"
fi
git -C "$work/utm" checkout --detach "$utm_commit"
test "$(git -C "$work/utm" rev-parse HEAD)" = "$utm_commit"
python3 "$repo_root/build/linux-arm-interpreter/prepare-utm.py" "$work/utm"
cd "$work/utm"
NCPU=3 bash scripts/build_dependencies.sh -p "$platform" -a arm64 2>&1 | tee "$work/build.log"
case "$platform" in ios) family=iOS;; macos) family=macOS;; esac
sysroot="sysroot-$family-arm64"
mkdir -p "$output"
ditto "$sysroot/Frameworks" "$output/Frameworks"
ditto "$sysroot/share/qemu" "$output/qemu"
python3 "$repo_root/build/linux-arm-interpreter/verify-config.py" "build-$family-arm64/qemu-10.0.12-utm" "$output"
printf '%s\n' "$utm_commit" > "$output/utm-source-commit.txt"
if [ "$platform" = macos ]; then
    clang -std=c11 -Wall -Wextra -Wno-unused-parameter \
        "$repo_root/build/linux-arm/host-launcher.c" "$repo_root/app/Madeira/LinuxVMBridge.c" \
        -Wl,-rpath,@executable_path/Frameworks -o "$output/host-launcher"
    # Hardened runtime with library validation disabled only for ad-hoc CI
    # frameworks. No allow-jit, unsigned-executable-memory or debugger access.
    codesign --force --sign - --options runtime \
        --entitlements "$repo_root/build/linux-arm-interpreter/host.entitlements" "$output/host-launcher"
fi
