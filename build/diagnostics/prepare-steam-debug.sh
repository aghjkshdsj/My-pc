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
sudo install -m 644 build/diagnostics/read-steam-debug.py "$root/usr/local/lib/my-pc/steam_crash_summary.py"
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
            -ex 'printf "MYPC_TCTI_GDB_CODE_BEGIN\\n"' -ex 'x/4wx $pc' \\
            -ex 'printf "MYPC_TCTI_GDB_CODE_END\\n"' \\
            --args "$steam_root/steamrtarm64/steam" -clientbeta publicbeta \\
            -no-cef-sandbox -cef-disable-gpu -cef-ozone-platform=x11 "$@" || true
        echo MYPC_TCTI_GDB_FINISHED
        exit 33
    fi
'''
path.write_text(source.replace(anchor, debug + anchor))
path = pathlib.Path(sys.argv[1]) / 'usr/local/lib/my-pc/probe-steam.py'
source = path.read_text()
anchor = 'if not success:\n    diagnostics ='
assert source.count(anchor) == 1
source = source.replace(anchor, '''if not success and args.guest and 'my_pc_steam_gdb=1' in pathlib.Path('/proc/cmdline').read_text():
    from steam_crash_summary import summarize
    # Parse before the ordinary diagnostic tail truncates large mapping tables.
    print('MYPC_TCTI_GDB_RESULT ' + json.dumps(summarize((output / 'launch.log').read_text(errors='replace'))), flush=True)
''' + anchor)
path.write_text(source)
PY
sudo chroot "$root" dpkg-query -W > "$guest/packages.tsv"
sync
sudo umount "$root"
trap - EXIT
(cd "$guest" && sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS)
tar -Sczf build/diagnostics/output/steam-debug-guest.tar.gz -C "$guest" Image initrd.img rootfs.raw packages.tsv runtime.json SHA256SUMS
