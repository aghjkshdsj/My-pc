#!/bin/sh
# initramfs local-bottom hook. Only reserved My-pc launchers are replaced.
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "${1:-}" in prereqs) prereqs; exit 0;; esac
# The minimal initrd need not contain grep or BusyBox. Use shell built-ins.
read -r command_line </proc/cmdline
case " $command_line " in *" my_pc_graphics=virgl "*) ;; *) exit 0;; esac
echo 'MYPC_GRAPHICS_HOOK_SEEN=1' >/dev/console
set -eu
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
trap fail EXIT
test -n "${rootmnt:-}" && test -d "$rootmnt/usr/local"
cd /my-pc-graphics
root_command sha256sum -c SHA256SUMS >/dev/null
# Reject linked directories before touching any reserved file. No user home,
# account, Steam installation, game or downloaded package path is writable here.
for directory in usr usr/local usr/local/bin usr/local/lib usr/local/lib/my-pc usr/local/lib/my-pc/steam-bin; do
    test -d "$rootmnt/$directory" && test ! -L "$rootmnt/$directory"
done
for file in usr/local/bin/my-pc-desktop usr/local/bin/my-pc-steam usr/local/lib/my-pc/steam-bin/taskset; do
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
root_command sync
echo 'MYPC_GRAPHICS_UPDATE_OK=1' >/dev/console
trap - EXIT
