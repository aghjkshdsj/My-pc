#!/bin/bash
# Patch only My-pc scripts in an isolated, account-free CI disk. No Valve files.
set -euo pipefail
test "$(uname -m)" = aarch64
guest=build/linux-arm-gpu/output/steam-guest
root=build/linux-arm-gpu/steam-mount
test -f "$guest/rootfs.raw"
mkdir -p "$root"
sudo mount -o loop "$guest/rootfs.raw" "$root"
trap 'sudo umount "$root"' EXIT
sudo install -m 644 build/linux-arm-gpu/steam_gpu.py "$root/usr/local/lib/my-pc/steam_gpu.py"
sudo python3 - "$root" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ('usr/local/bin/my-pc-desktop', 'usr/local/bin/my-pc-steam'):
    path = root / name
    source = path.read_text()
    anchor = 'export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe\n'
    assert source.count(anchor) == 1
    source = source.replace(anchor, 'unset LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER\n')
    if name.endswith('my-pc-steam'):
        assert source.count('-cef-disable-gpu ') == 1
        source = source.replace('-cef-disable-gpu ', '')
    path.write_text(source)
path = root / 'usr/local/lib/my-pc/probe-steam.py'
source = path.read_text()
anchor = '        if success and args.guest:\n'
assert source.count(anchor) == 1
source = source.replace(anchor, anchor + '''            from steam_gpu import accelerated_login
            accelerated_login()
''')
path.write_text(source)
PY
sync
sudo umount "$root"
trap - EXIT
(cd "$guest" && sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS)
# This is the bare guest before any Valve client downloads.
tar -Sczf build/linux-arm-gpu/output/steam-gpu-guest.tar.gz -C "$guest" Image initrd.img rootfs.raw packages.tsv runtime.json SHA256SUMS
