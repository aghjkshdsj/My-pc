#!/bin/sh
set -eu
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=Openbox
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
xset s off -dpms
xsetroot -solid '#162334'
openbox &
if grep -qw my_pc_desktop_test=1 /proc/cmdline; then
    exec python3 /usr/local/lib/my-pc/desktop-test.py
fi
pulseaudio --start --exit-idle-time=-1 || true
if grep -qw my_pc_steam_test=1 /proc/cmdline; then
    exec python3 -u /usr/local/lib/my-pc/probe-steam.py "$HOME/steam-probe" --guest --timeout 1200 >/dev/ttyAMA0 2>&1
fi
while :; do
    xterm -T 'Steam ARM64' -fa 'DejaVu Sans Mono' -fs 11 -geometry 100x28+20+20 \
        -e sh -c '/usr/local/bin/my-pc-steam; echo "Steam closed. Press Enter to reopen."; read answer'
    sleep 1
done
