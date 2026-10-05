#!/bin/bash
# Hosted CPU fault-injection engine only. Never use this binary for iOS or performance claims.
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
output="$project/out/display-fault-qemu"
test ! -e "$output"
mkdir -p "$output"
cd "$output"
curl --fail --location --retry 3 -o qemu-10.0.12-utm.tar.xz https://github.com/utmapp/qemu/releases/download/v10.0.12-utm/qemu-10.0.12-utm.tar.xz
echo '7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a  qemu-10.0.12-utm.tar.xz' > UPSTREAM-SHA256SUMS
sha256sum -c UPSTREAM-SHA256SUMS
mkdir source
tar -xf qemu-10.0.12-utm.tar.xz -C source --strip-components=1
python3 "$project/tools/patch_qemu_display_fault_control.py" "$output/source" "$output/patch"
python3 -m venv "$output/build-tools"
"$output/build-tools/bin/pip" install 'meson==1.9.1' 'ninja==1.13.0'
export PATH="$output/build-tools/bin:$PATH"
mkdir build
cd build
../source/configure --target-list=aarch64-softmmu --without-default-features --enable-tcg --enable-pixman --disable-docs --disable-tools --disable-guest-agent --disable-werror
ninja qemu-system-aarch64
cd "$output"
mkdir corresponding-source
cp qemu-10.0.12-utm.tar.xz UPSTREAM-SHA256SUMS source/COPYING corresponding-source/
cp -r patch corresponding-source/
cp "$project/tools/build_display_fault_qemu.sh" "$project/tools/patch_qemu_display_fault_control.py" "$project/tools/patch_linux_display_completion.py" corresponding-source/
cp "$project/../.github/workflows/steamos-display-completion-control.yml" corresponding-source/
cp build/config.log build/config-host.mak corresponding-source/
"$output/build-tools/bin/pip" freeze > corresponding-source/build-tools-versions.txt
tar -czf Display-Fault-QEMU-Corresponding-Source.tar.gz corresponding-source
sha256sum build/qemu-system-aarch64 Display-Fault-QEMU-Corresponding-Source.tar.gz > SHA256SUMS
