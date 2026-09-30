#!/bin/sh
set -eu
exec >/dev/ttyAMA0 2>&1
fail() { echo "MYPC_LINUX_FAIL:$*"; sync; poweroff -f; exit 1; }
test "$(uname -m)" = aarch64 || fail architecture
echo 'MYPC_LINUX_ARM64_BOOTED'
online_cpus=$(nproc)
echo "MYPC_LINUX_CPU_COUNT=$online_cpus"
for argument in $(cat /proc/cmdline); do
    case "$argument" in
        my_pc_expected_cpus=*)
            expected_cpus=${argument#*=}
            test "$online_cpus" = "$expected_cpus" || fail cpu_count
            ;;
    esac
done
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
sync
echo 'MYPC_LINUX_SMOKE_OK'
if grep -Eq 'my_pc_(desktop|steam)_test=1' /proc/cmdline; then
    # Let multi-user.target finish. The host verifies actual X11 input and
    # then uses the same QMP power button command as the iPhone app.
    exit 0
fi
systemctl poweroff
