#!/bin/sh
set -eu
exec >/dev/ttyAMA0 2>&1
fail() { echo "MYPC_LINUX_FAIL:$*"; sync; poweroff -f; exit 1; }
test "$(uname -m)" = aarch64 || fail architecture
echo 'MYPC_LINUX_ARM64_BOOTED'
test -w /var/lib || fail root_read_only
if test -f /var/lib/my-pc-persistence; then
    test "$(cat /var/lib/my-pc-persistence)" = my-pc-arm-linux || fail persistence_content
    echo 'MYPC_LINUX_PERSISTENCE_OK'
else
    echo my-pc-arm-linux > /var/lib/my-pc-persistence
    sync
    echo 'MYPC_LINUX_PERSISTENCE_WRITTEN'
fi
curl --fail --max-time 45 http://10.0.2.2:18080/probe.txt | grep -qx my-pc-network-ok || fail network
echo 'MYPC_LINUX_NETWORK_OK'
if grep -qw my_pc_desktop_test=1 /proc/cmdline; then
    attempts=0
    while ! test -f /home/steam/.desktop-test-passed; do
        attempts=$((attempts + 1))
        test "$attempts" -lt 240 || fail desktop_input_timeout
        sleep 1
    done
    rm /home/steam/.desktop-test-passed
    echo 'MYPC_LINUX_DESKTOP_OK'
fi
sync
echo 'MYPC_LINUX_SMOKE_OK'
systemctl poweroff
