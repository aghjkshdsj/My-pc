#!/bin/sh
# initramfs local-bottom hook. Only reserved My-pc launchers are replaced.
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "${1:-}" in prereqs) prereqs; exit 0;; esac
# The minimal initrd need not contain grep or BusyBox. Use shell built-ins.
read -r command_line </proc/cmdline
case " $command_line " in *" my_pc_graphics=virgl "*|*" my_pc_graphics=software "*) ;; *) exit 0;; esac
echo 'MYPC_GRAPHICS_HOOK_SEEN=1' >/dev/console
set -eu
read -r update_started ignored </proc/uptime
report_timing() {
    read -r update_finished ignored </proc/uptime
    echo "MYPC_GRAPHICS_UPDATE_TIMING $update_started $update_finished" >/dev/console
}
echo 'MYPC_GRAPHICS_UPDATE_PHASE=shell-ready' >/dev/console
root_command() {
    command=$1
    shift
    "$rootmnt/lib/ld-linux-aarch64.so.1" \
        --library-path "$rootmnt/lib/aarch64-linux-gnu:$rootmnt/usr/lib/aarch64-linux-gnu" \
        "$rootmnt/usr/bin/$command" "$@"
}
fail() {
    echo 'MYPC_GRAPHICS_UPDATE_FAILED: reserved startup files could not be updated' >/dev/console
    root_command sync || true
    poweroff -f || reboot -f || true
    exit 1
}
# klibc dash accepts numeric traps, but rejects the EXIT signal name.
trap fail 0
echo 'MYPC_GRAPHICS_UPDATE_PHASE=validate-root' >/dev/console
test -n "${rootmnt:-}" || fail
test -d "$rootmnt/usr/local" || fail
cd /my-pc-graphics
echo 'MYPC_GRAPHICS_UPDATE_PHASE=verify-payload' >/dev/console
# The app has verified the complete initrd. Validate its installed-file tables
# before using them, but do not rescan unused bundled binaries on a reuse boot.
metadata_count=0
while read -r checksum name; do
    case "$name" in
        installed-SHA256SUMS|installed-MODES|installed-LINKS)
            printf '%s  %s\n' "$checksum" "$name"
            metadata_count=$((metadata_count + 1))
            ;;
    esac
done <SHA256SUMS >installed-reuse-checks
test "$metadata_count" -eq 3
root_command sha256sum -c installed-reuse-checks >/dev/null
# Reject linked directories before touching any reserved file. No user home,
# account, Steam installation, game or downloaded package path is writable here.
for directory in usr usr/local usr/local/bin usr/local/lib usr/local/lib/my-pc usr/local/lib/my-pc/steam-bin; do
    test -d "$rootmnt/$directory" && test ! -L "$rootmnt/$directory"
done
# Avoid recopies and a global disk sync when every reserved installed byte,
# file type, permission, owner and link already matches this verified payload.
# The comparison output lives in the initramfs, never on the persistent disk.
reuse_installed() {
    for directory in usr/local/lib/my-pc/hardware-tests usr/local/lib/my-pc/controller etc etc/udev etc/udev/rules.d etc/systemd etc/systemd/system etc/systemd/system/multi-user.target.wants; do
        test -d "$rootmnt/$directory" && test ! -L "$rootmnt/$directory" || return 1
    done
    cd "$rootmnt"
    set --
    while read -r properties name; do set -- "$@" "$name"; done </my-pc-graphics/installed-MODES
    root_command stat -c '%u:%g:%f  %n' -- "$@" >/my-pc-graphics/installed-actual-modes 2>/dev/null || return 1
    root_command cmp -s /my-pc-graphics/installed-MODES /my-pc-graphics/installed-actual-modes || return 1
    root_command sha256sum -c /my-pc-graphics/installed-SHA256SUMS >/dev/null 2>&1 || return 1
    # The bulk stat above already established each symlink's type and owner.
    # Read all targets in one process rather than launching a guest process
    # per link. Both comparison files live only in the initramfs.
    set --
    while read -r name target; do
        set -- "$@" "$name"
        printf '%s\n' "$target"
    done </my-pc-graphics/installed-LINKS >/my-pc-graphics/installed-expected-links
    if test "$#" -gt 0; then
        root_command readlink -- "$@" >/my-pc-graphics/installed-actual-links || return 1
        root_command cmp -s /my-pc-graphics/installed-expected-links /my-pc-graphics/installed-actual-links || return 1
    fi
}
if (reuse_installed); then
    echo 'MYPC_GRAPHICS_UPDATE_REUSED=1' >/dev/console
    report_timing
    echo 'MYPC_GRAPHICS_UPDATE_OK=1' >/dev/console
    trap - 0
    exit 0
fi
# Every source byte is verified before the first persistent write. A corrupt
# unused source cannot damage a matching install or be used for a repair.
root_command sha256sum -c SHA256SUMS >/dev/null
for file in usr/local/bin/my-pc-desktop usr/local/bin/my-pc-steam usr/local/lib/my-pc/steam-bin/taskset; do
    echo 'MYPC_GRAPHICS_UPDATE_PHASE=replace-launcher' >/dev/console
    destination="$rootmnt/$file"
    test -f "$destination" && test ! -L "$destination"
    test ! -L "$destination.my-pc-before-metal"
    if test ! -e "$destination.my-pc-before-metal"; then
        root_command cp -p "$destination" "$destination.my-pc-before-metal"
    fi
    test ! -e "$destination.my-pc-metal-new"
    root_command cp "$file" "$destination.my-pc-metal-new"
    root_command chmod 755 "$destination.my-pc-metal-new"
    root_command mv -f "$destination.my-pc-metal-new" "$destination"
done
echo 'MYPC_GRAPHICS_UPDATE_PHASE=install-diagnostics' >/dev/console
# Only this reserved test directory is added. Never install global FEX files,
# touch the owner's home, or change Steam's downloaded compatibility tools.
destination="$rootmnt/usr/local/lib/my-pc/hardware-tests"
test ! -L "$destination"
root_command mkdir -p "$destination"
root_command cp -a hardware-tests/. "$destination/"
echo 'MYPC_GRAPHICS_UPDATE_PHASE=install-controller' >/dev/console
destination="$rootmnt/usr/local/lib/my-pc/controller"
test ! -L "$destination"
root_command mkdir -p "$destination"
for name in controller.py controller-ci.py my-pc-controller.service 70-my-pc-diagnostics.rules; do test ! -L "$destination/$name"; done
root_command cp -a controller/. "$destination/"
# Permit only Steam's unprivileged desktop user to open the diagnostic port.
# udev processes the virtio port after this initramfs hook, on normal boot.
for directory in etc etc/udev etc/udev/rules.d; do
    test ! -L "$rootmnt/$directory"
    root_command mkdir -p "$rootmnt/$directory"
done
rule="$rootmnt/etc/udev/rules.d/70-my-pc-diagnostics.rules"
test ! -L "$rule"
root_command cp controller/70-my-pc-diagnostics.rules "$rule"
# Add only the named bridge unit and its normal target dependency.
for directory in etc etc/systemd etc/systemd/system etc/systemd/system/multi-user.target.wants; do
    test ! -L "$rootmnt/$directory"
    root_command mkdir -p "$rootmnt/$directory"
done
unit="$rootmnt/etc/systemd/system/my-pc-controller.service"
test ! -L "$unit"
root_command cp controller/my-pc-controller.service "$unit"
link="$rootmnt/etc/systemd/system/multi-user.target.wants/my-pc-controller.service"
if test -L "$link"; then
    test "$(root_command readlink "$link")" = ../my-pc-controller.service
else
    test ! -e "$link"
    root_command ln -s ../my-pc-controller.service "$link"
fi
echo 'MYPC_GRAPHICS_UPDATE_PHASE=sync' >/dev/console
root_command sync
report_timing
echo 'MYPC_GRAPHICS_UPDATE_OK=1' >/dev/console
trap - 0
