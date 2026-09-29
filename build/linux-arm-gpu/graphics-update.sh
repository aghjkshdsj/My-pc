#!/bin/sh
# initramfs local-bottom hook. Only reserved My-pc launchers are replaced.
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "${1:-}" in prereqs) prereqs; exit 0;; esac
grep -qw my_pc_graphics=virgl /proc/cmdline || exit 0
set -eu
fail() {
    echo 'MYPC_GRAPHICS_UPDATE_FAILED: reserved startup files could not be updated' >/dev/console
    /bin/busybox poweroff -f
    exit 1
}
trap fail EXIT
test -n "${rootmnt:-}" && test -d "$rootmnt/usr/local"
cd /my-pc-graphics
/bin/busybox sha256sum -c SHA256SUMS >/dev/null
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
        /bin/busybox cp -p "$destination" "$destination.my-pc-before-metal"
    fi
    test ! -e "$destination.my-pc-metal-new"
    /bin/busybox cp "$file" "$destination.my-pc-metal-new"
    /bin/busybox chmod 755 "$destination.my-pc-metal-new"
    /bin/busybox mv -f "$destination.my-pc-metal-new" "$destination"
done
echo 'MYPC_GRAPHICS_UPDATE_OK=1' >/dev/console
trap - EXIT
