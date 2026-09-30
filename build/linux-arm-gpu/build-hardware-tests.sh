#!/bin/bash
# Build our workloads and bundle unmodified upstream FEX binaries privately.
# This does not install a system FEX, alter Steam's FEX, or rebuild FEX source.
set -euo pipefail
test "$(uname -m)" = aarch64
output=build/linux-arm-gpu/output/hardware-tests
test ! -e "$output"
mkdir -p "$output/bin" "$output/fex" "$output/native" "$output/notices"
sudo apt-get update
sudo apt-get install -y --no-install-recommends gcc gcc-x86-64-linux-gnu libc6-dev-amd64-cross mmdebstrap zstd
gcc -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -pthread \
    build/linux-arm-gpu/hardware-bench.c -ldl -o "$output/bin/hardware-bench-arm64"
x86_64-linux-gnu-gcc -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -pthread \
    build/linux-arm-gpu/hardware-bench.c -ldl -o "$output/bin/hardware-bench-x86_64"
python3 - "$output" <<'PY'
import hashlib, pathlib, urllib.request
out = pathlib.Path(__import__('sys').argv[1])
url = 'https://ppa.launchpadcontent.net/fex-emu/fex/ubuntu/pool/main/f/fex-emu-armv8.0/fex-emu-armv8.0_2609.1-1~n_arm64.deb'
data = urllib.request.urlopen(url, timeout=60).read()
assert len(data) == 3284698
assert hashlib.sha256(data).hexdigest() == 'c48d651e2ba1439f66ae9f69277237a90b66977f67609e63679b2eedfb049888'
(out / 'fex.deb').write_bytes(data)
key = urllib.request.urlopen('https://ftp-master.debian.org/keys/archive-key-13.asc', timeout=60).read()
assert hashlib.sha256(key).hexdigest() == '6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7'
(out / 'debian-key.asc').write_bytes(key)
PY
gpg --batch --yes --dearmor --output "$output/debian-keyring.gpg" "$output/debian-key.asc"
dpkg-deb -x "$output/fex.deb" "$output/fex"
rm "$output/fex.deb"
# Only headless tools needed for these tests. All retained files are unchanged.
for name in FEXConfig FEXRootFSFetcher FEXGetConfig FEXBash; do rm "$output/fex/usr/bin/$name"; done
# No binfmt handler, apt sources, system packages or global FEX config changed.
sudo mmdebstrap --variant=extract --architectures=amd64 \
    --keyring="$PWD/$output/debian-keyring.gpg" \
    --include=libc6,libstdc++6,libx11-6 trixie "$output/rootfs" https://deb.debian.org/debian
rm "$output/debian-key.asc" "$output/debian-keyring.gpg"
sudo chown -R "$(id -u):$(id -g)" "$output/rootfs"
# Extract-only roots do not run Debian's usr-merge maintainer scripts.
for name in lib lib64 bin sbin; do
    if [ ! -e "$output/rootfs/$name" ] && [ ! -L "$output/rootfs/$name" ]; then
        ln -s "usr/$name" "$output/rootfs/$name"
    fi
done
test -r "$output/rootfs/lib64/ld-linux-x86-64.so.2"
mkdir -p "$output/rootfs/usr/lib/x86_64-linux-gnu"
# Private diagnostic root only: directly load the supplied x86 thunk binaries.
# EGL forwards GL procedures through the GL thunk. No x86 software Mesa is
# installed here, so this test cannot silently pass using that renderer.
cp "$output/fex/usr/share/fex-emu/GuestThunks/libGL-guest.so" "$output/rootfs/usr/lib/x86_64-linux-gnu/libGL.so.1"
cp "$output/fex/usr/share/fex-emu/GuestThunks/libEGL-guest.so" "$output/rootfs/usr/lib/x86_64-linux-gnu/libEGL.so.1"
# The old ARM guest lacks libOpenGL.so.0; retain the signed Debian package's
# library and notices locally without changing its installed system packages.
(cd "$output" && apt-get download libopengl0)
for package in "$output"/libopengl0_*.deb; do dpkg-deb -x "$package" "$output/native"; rm "$package"; done
cp build/linux-arm-gpu/hardware-test.py "$output/"
cp build/linux-arm-gpu/hardware-keys.py "$output/"
cp build/linux-arm-gpu/hardware-test-ci.py "$output/"
python3 - "$output" <<'PY'
import hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
metadata = {'schema': 1, 'fex_version': '2609.1-1~n',
            'fex_deb_sha256': 'c48d651e2ba1439f66ae9f69277237a90b66977f67609e63679b2eedfb049888',
            'fex_source': 'https://github.com/FEX-Emu/FEX/tree/FEX-2609',
            'gpu_path': 'x86 EGL/GL forwarding to ARM Mesa virgl; host ANGLE/Metal',
            'workload_sha256': hashlib.sha256(pathlib.Path('build/linux-arm-gpu/hardware-bench.c').read_bytes()).hexdigest()}
(out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
import importlib.util
spec = importlib.util.spec_from_file_location('bench', 'build/linux-arm-gpu/hardware-test.py')
bench = importlib.util.module_from_spec(spec); spec.loader.exec_module(bench)
# Compute each worker's result once, then the XOR for every supported count.
checksums = {}
for iterations in (10000, 1000000):
    combined = 0
    for workers in range(1,65):
        value = workers
        for _ in range(iterations):
            value ^= value >> 12; value ^= (value << 25) & bench.MASK; value ^= value >> 27
            value = value * 2685821657736338717 & bench.MASK
        combined ^= value
        checksums[f'{workers}:{iterations}'] = f'{combined:016x}'
(out / 'checksums.json').write_text(json.dumps(checksums, sort_keys=True) + '\n')
(out / 'notices/README.txt').write_text('My-pc diagnostic runtime. FEX binaries and thunks are unmodified.\n'
    'FEX source: https://github.com/FEX-Emu/FEX/tree/FEX-2609\n'
    'FEX package notices: ../fex/usr/share/doc/fex-emu-armv8.0/copyright\n'
    'Root libraries are Debian trixie amd64 packages; notices: ../rootfs/usr/share/doc/\n'
    'This is a GLES test; it does not validate Vulkan, DirectX or Proton games.\n')
PY
# Real native/FEX CPU smoke checks on the ARM builder, including deterministic
# checksums. Graphics is subsequently checked in the production Metal VM.
MYPC_HARDWARE_CI=1 python3 build/linux-arm-gpu/test-hardware-runtime.py "$output" --cpu-only
echo MYPC_HARDWARE_TEST_PAYLOAD_BUILT
