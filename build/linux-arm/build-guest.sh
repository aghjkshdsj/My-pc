#!/bin/bash
# Run on an ARM64 Linux builder. Debian/glibc can later host Valve's ARM client.
set -euo pipefail
test "$(uname -m)" = aarch64
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$repo_root/build/linux-arm/guest-work"
output="$repo_root/build/linux-arm/output/guest"
mkdir -p "$work" "$output"
root="$work/root"
test ! -e "$root" || { echo 'Use a fresh guest build directory' >&2; exit 1; }
sudo debootstrap --arch=arm64 --variant=minbase --include=ca-certificates trixie "$root" https://deb.debian.org/debian
sudo install -m 755 "$repo_root/build/linux-arm/guest-smoke.sh" "$root/usr/local/sbin/my-pc-smoke"
sudo tee "$root/usr/sbin/policy-rc.d" >/dev/null <<'EOF'
#!/bin/sh
exit 101
EOF
sudo chmod 755 "$root/usr/sbin/policy-rc.d"
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    linux-image-arm64 initramfs-tools systemd-sysv systemd-resolved libpam-systemd \
    iproute2 iputils-ping curl ca-certificates kmod dbus-x11 python3 python3-xlib procps \
    xserver-xorg-core xserver-xorg-input-libinput xinit xauth x11-xserver-utils x11-utils scrot \
    openbox xterm fonts-dejavu-core pulseaudio libasound2-plugins \
    libgl1-mesa-dri libglx-mesa0 libegl-mesa0 libegl1 mesa-vulkan-drivers libvulkan1 \
    libxrandr2 libxinerama1 libxcursor1 libxcomposite1 libxdamage1 libxtst6 \
    libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
    libgtk-3-0t64 libgtk2.0-0t64 libsdl2-2.0-0 libgbm1 libdrm2 libibus-1.0-5 libnm0 libopenal1 \
    libpipewire-0.3-0t64 libpulse0 libva2
sudo install -d "$root/usr/local/lib/my-pc"
sudo install -d "$root/usr/local/lib/my-pc/steam-bin"
sudo install -m 755 "$repo_root/build/linux-arm/steam-bin/taskset" "$root/usr/local/lib/my-pc/steam-bin/taskset"
sudo install -m 755 "$repo_root/build/linux-arm/steam-arm-fetch.py" "$root/usr/local/lib/my-pc/"
sudo install -m 755 "$repo_root/build/linux-arm/steam-session.sh" "$root/usr/local/bin/my-pc-steam"
sudo install -m 755 "$repo_root/build/linux-arm/desktop-session.sh" "$root/usr/local/bin/my-pc-desktop"
sudo install -m 755 "$repo_root/build/linux-arm/desktop-test.py" "$root/usr/local/lib/my-pc/"
sudo install -m 755 "$repo_root/build/linux-arm/probe-steam.py" "$root/usr/local/lib/my-pc/"
sudo chroot "$root" useradd --create-home --shell /bin/bash --groups audio,video,render,input,dialout steam
sudo install -d "$root/etc/systemd/system/getty@tty1.service.d"
sudo tee "$root/etc/systemd/system/getty@tty1.service.d/steam.conf" >/dev/null <<'EOF'
[Unit]
ConditionKernelCommandLine=!my_pc_smoke=1
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin steam --noclear %I $TERM
EOF
sudo tee "$root/home/steam/.bash_profile" >/dev/null <<'EOF'
if [ "$(tty)" = /dev/tty1 ] && [ -z "$DISPLAY" ]; then
    exec startx /usr/bin/dbus-run-session /usr/local/bin/my-pc-desktop -- :0 vt1 -keeptty -nolisten tcp
fi
EOF
sudo chroot "$root" chown steam:steam /home/steam/.bash_profile
sudo chroot "$root" systemctl enable getty@tty1.service
sudo mkdir -p "$root/etc/systemd/network" "$root/etc/systemd/system/multi-user.target.wants"
sudo tee "$root/etc/systemd/network/20-wired.network" >/dev/null <<'EOF'
[Match]
Name=en* eth*
[Network]
DHCP=yes
EOF
sudo tee "$root/etc/systemd/system/my-pc-smoke.service" >/dev/null <<'EOF'
[Unit]
Description=My-pc ARM Linux boot verification
After=network-online.target
Wants=network-online.target
ConditionKernelCommandLine=|my_pc_smoke=1
ConditionKernelCommandLine=|my_pc_desktop_test=1
ConditionKernelCommandLine=|my_pc_steam_test=1
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/my-pc-smoke
StandardOutput=journal+console
StandardError=journal+console
[Install]
WantedBy=multi-user.target
EOF
sudo chroot "$root" systemctl enable systemd-networkd systemd-networkd-wait-online systemd-resolved my-pc-smoke
sudo ln -sf /run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"
sudo tee "$root/etc/fstab" >/dev/null <<'EOF'
/dev/vda / ext4 defaults 0 1
EOF
sudo chroot "$root" update-initramfs -u -k all
sudo chroot "$root" apt-get clean
sudo chroot "$root" dpkg-query -W > "$output/packages.tsv"
sudo cp "$root"/boot/vmlinuz-* "$output/Image"
sudo cp "$root"/boot/initrd.img-* "$output/initrd.img"
truncate -s 12G "$output/rootfs.raw"
sudo mkfs.ext4 -F -L my-pc-linux -d "$root" "$output/rootfs.raw"
sudo chown -R "$(id -u):$(id -g)" "$output"
printf '%s\n' '{"schema":1,"architecture":"aarch64","distribution":"debian-trixie","diskGiB":12,"purpose":"ARM64 desktop; full Steam downloaded from Valve at first launch","renderer":"software"}' > "$output/runtime.json"
cd "$output"
sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS
