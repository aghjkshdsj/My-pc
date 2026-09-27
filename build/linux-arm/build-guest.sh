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
sudo chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends linux-image-arm64 initramfs-tools systemd-sysv systemd-resolved iproute2 iputils-ping curl ca-certificates kmod
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
ConditionKernelCommandLine=my_pc_smoke=1
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
truncate -s 4G "$output/rootfs.raw"
sudo mkfs.ext4 -F -L my-pc-linux -d "$root" "$output/rootfs.raw"
sudo chown -R "$(id -u):$(id -g)" "$output"
printf '%s\n' '{"schema":1,"architecture":"aarch64","distribution":"debian-trixie","purpose":"Linux bring-up; Steam not installed"}' > "$output/runtime.json"
cd "$output"
sha256sum Image initrd.img rootfs.raw packages.tsv runtime.json > SHA256SUMS
