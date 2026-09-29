#!/bin/bash
# GPL-3.0-or-later. Only a fresh, account-free CI guest is modified.
set -euo pipefail
test "$(uname -m)" = aarch64
guest=build/diagnostics/output/guest
root=build/diagnostics/guest-mount
test -f "$guest/rootfs.raw"
mkdir -p "$root"
sudo mount -o loop "$guest/rootfs.raw" "$root"
trap 'sudo umount "$root"' EXIT
sudo unlink "$root/etc/resolv.conf"
sudo install -m 644 /etc/resolv.conf "$root/etc/resolv.conf"
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gdb
sudo chroot "$root" apt-get clean
sudo rm "$root/etc/resolv.conf"
sudo ln -s /run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"
sudo python3 - "$root" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1]) / 'usr/local/bin/my-pc-steam'
source = path.read_text()
anchor = '    "$steam_root/steamrtarm64/steam" -clientbeta publicbeta \\\n'
assert source.count(anchor) == 1, 'Verified launcher anchor changed'
debug = '''    if grep -qw my_pc_steam_gdb=1 /proc/cmdline; then
        gdb --batch --return-child-result \\
            -ex 'set pagination off' -ex 'set print thread-events off' \\
            -ex run -ex 'printf "MYPC_TCTI_GDB_PC=%p\\n", $pc' \\
            -ex 'bt 12' -ex 'info proc mappings' \\
            --args "$steam_root/steamrtarm64/steam" -clientbeta publicbeta \\
            -no-cef-sandbox -cef-disable-gpu -cef-ozone-platform=x11 "$@" || true
        echo MYPC_TCTI_GDB_FINISHED
        exit 33
    fi
'''
path.write_text(source.replace(anchor, debug + anchor))
PY
sudo chroot "$root" dpkg-query -W > "$guest/packages.tsv"
sync
sudo umount "$root"
trap - EXIT
(cd "$guest" && sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS)
tar -Sczf build/diagnostics/output/steam-debug-guest.tar.gz -C "$guest" Image initrd.img rootfs.raw packages.tsv runtime.json SHA256SUMS
