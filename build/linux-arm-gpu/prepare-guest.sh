#!/bin/bash
# Alter only a fresh, isolated copy of the verified CI guest disk.
set -euo pipefail
test "$(uname -m)" = aarch64
guest=build/linux-arm-gpu/output/guest
root=build/linux-arm-gpu/guest-mount
test -f "$guest/rootfs.raw"
mkdir -p "$root"
sudo mount -o loop "$guest/rootfs.raw" "$root"
trap 'sudo umount "$root"' EXIT
sudo unlink "$root/etc/resolv.conf"
sudo install -m 644 /etc/resolv.conf "$root/etc/resolv.conf"
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libgles2 mesa-utils
sudo chroot "$root" apt-get clean
sudo rm "$root/etc/resolv.conf"
sudo ln -s /run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"
sudo install -m 755 build/linux-arm-gpu/guest-gpu-probe.py "$root/usr/local/lib/my-pc/guest-gpu-probe.py"
sudo python3 - "$root" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
session = root / 'usr/local/bin/my-pc-desktop'
source = session.read_text()
anchor = 'export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe\n'
assert source.count(anchor) == 1
source = source.replace(anchor, '''if grep -qw my_pc_gpu_test=1 /proc/cmdline; then
    unset LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER
else
    export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
fi
''')
anchor = 'openbox &\n'
assert source.count(anchor) == 1
session.write_text(source.replace(anchor, anchor + '''if grep -qw my_pc_gpu_test=1 /proc/cmdline; then
    exec python3 -u /usr/local/lib/my-pc/guest-gpu-probe.py >/dev/ttyAMA0 2>&1
fi
'''))
smoke = root / 'usr/local/sbin/my-pc-smoke'
source = smoke.read_text()
assert "my_pc_(desktop|steam)_test=1" in source
smoke.write_text(source.replace('my_pc_(desktop|steam)_test=1', 'my_pc_(desktop|steam|gpu)_test=1'))
PY
sudo chroot "$root" dpkg-query -W > "$guest/packages.tsv"
sync
sudo umount "$root"
trap - EXIT
printf '%s\n' '{"schema":1,"architecture":"aarch64","purpose":"Isolated virgl shader and display test; no account","renderer":"virgl-test"}' > "$guest/runtime.json"
(cd "$guest" && sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS)
tar -Sczf build/linux-arm-gpu/output/gpu-test-guest.tar.gz -C "$guest" Image initrd.img rootfs.raw packages.tsv runtime.json SHA256SUMS
