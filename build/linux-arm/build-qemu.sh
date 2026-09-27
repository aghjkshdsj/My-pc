#!/bin/bash
set -euo pipefail
platform="${1:-ios}"
case "$platform" in ios|macos) ;; *) echo 'Expected ios or macos' >&2; exit 2;; esac
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$repo_root/build/linux-arm/work-$platform"
utm_commit=7eadb056ae0f91d979059544d0ddcd2d5a40be92
mkdir -p "$work"
if [ ! -d "$work/utm/.git" ]; then
    git clone --filter=blob:none --no-checkout https://github.com/utmapp/UTM.git "$work/utm"
fi
git -C "$work/utm" checkout --detach "$utm_commit"
test "$(git -C "$work/utm" rev-parse HEAD)" = "$utm_commit"
python3 "$repo_root/build/linux-arm/prepare-utm.py" "$work/utm"
cd "$work/utm"
NCPU=3 bash scripts/build_dependencies.sh -p "$platform" -a arm64 2>&1 | tee "$work/build.log"
case "$platform" in ios) sysroot=sysroot-iOS-arm64;; macos) sysroot=sysroot-macOS-arm64;; esac
test -f "$sysroot/Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu" || test -f "$sysroot/Frameworks/qemu-aarch64-softmmu.framework/Versions/A/qemu-aarch64-softmmu"
mkdir -p "$repo_root/build/linux-arm/output/$platform"
ditto "$sysroot/Frameworks" "$repo_root/build/linux-arm/output/$platform/Frameworks"
ditto "$sysroot/share/qemu" "$repo_root/build/linux-arm/output/$platform/qemu"
find "$sysroot/Frameworks" -type f -perm +111 -exec otool -L {} \; > "$repo_root/build/linux-arm/output/$platform/dependencies.txt"
printf '%s\n' "$utm_commit" > "$repo_root/build/linux-arm/output/$platform/utm-source-commit.txt"
