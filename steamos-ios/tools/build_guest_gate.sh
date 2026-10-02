#!/bin/bash
# Source-built disposable Linux CPU gate; it is not a SteamOS distribution.
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
output="$project/out/source-guest"
mkdir -p "$output"
cd "$output"
test ! -e linux-6.12.111
test ! -e busybox-1.38.0
curl --fail --location --retry 3 -o linux-6.12.111.tar.xz https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.12.111.tar.xz
curl --fail --location --retry 3 -o busybox-1.38.0.tar.bz2 https://busybox.net/downloads/busybox-1.38.0.tar.bz2
cat > UPSTREAM-SHA256SUMS <<'EOF'
9e59dc67624188fa12a6601f9598499cd6662a9066be572b59f935e3d7849810  linux-6.12.111.tar.xz
34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2  busybox-1.38.0.tar.bz2
EOF
sha256sum -c UPSTREAM-SHA256SUMS
tar -xf linux-6.12.111.tar.xz
tar -xf busybox-1.38.0.tar.bz2
cd linux-6.12.111
make ARCH=arm64 tinyconfig
for option in SMP MULTIUSER PRINTK TTY SERIAL_AMBA_PL011 SERIAL_AMBA_PL011_CONSOLE ARM_GIC ARM_GIC_V3 ARM_PSCI_FW ARM_ARCH_TIMER ARCH_VIRT OF BINFMT_ELF BINFMT_SCRIPT PROC_FS SYSFS TMPFS SHMEM FUTEX EPOLL EVENTFD TIMERFD POSIX_TIMERS BLK_DEV_INITRD RD_GZIP DEVTMPFS DEVTMPFS_MOUNT; do
    scripts/config --enable "$option"
done
scripts/config --enable ARM64_4K_PAGES --disable ARM64_16K_PAGES --disable ARM64_64K_PAGES --set-val NR_CPUS 2
scripts/config --disable DEBUG_INFO --disable MODULES --disable SECURITY --disable RANDOMIZE_BASE
make ARCH=arm64 olddefconfig
make ARCH=arm64 -j"$(nproc)" Image
cp .config "$output/kernel.config"
cd "$output/busybox-1.38.0"
make allnoconfig
for option in STATIC ASH SH_IS_ASH MOUNT UMOUNT POWEROFF CAT ECHO; do
    "$output/linux-6.12.111/scripts/config" --file .config --enable "$option"
done
make oldconfig < /dev/null
make -j"$(nproc)"
cp .config "$output/busybox.config"
gcc -static -std=c11 -O2 -Wall -Wextra -Werror -pthread "$project/Guest/abi_probe.c" -o "$output/mpc-abi"
python3 "$project/tools/make_initramfs.py" "$output/linux-6.12.111/arch/arm64/boot/Image" "$output/busybox-1.38.0/busybox" "$output/mpc-abi" "$output/payload"
python3 "$project/tools/run_kernel_gate.py" "$output/payload"
mkdir -p "$output/corresponding-source"
cp "$output/"*.tar.* "$output/UPSTREAM-SHA256SUMS" "$output/kernel.config" "$output/busybox.config" "$output/corresponding-source/"
cp "$project/Guest/abi_probe.c" "$project/Guest/init" "$project/tools/build_guest_gate.sh" "$project/tools/make_initramfs.py" "$project/tools/run_kernel_gate.py" "$output/corresponding-source/"
cp "$output/linux-6.12.111/COPYING" "$output/corresponding-source/Linux-COPYING"
cp "$output/busybox-1.38.0/LICENSE" "$output/corresponding-source/BusyBox-LICENSE"
tar -czf "$output/Linux-Gate-Corresponding-Source.tar.gz" -C "$output" corresponding-source
tar -czf "$output/Linux-Gate-Payload.tar.gz" -C "$output/payload" Image initramfs.cpio.gz payload-receipt.json kernel-test.json
(cd "$output" && sha256sum Linux-Gate-*.tar.gz > SHA256SUMS)
