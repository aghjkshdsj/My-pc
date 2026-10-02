#!/bin/bash
# Fresh generic ARM graphics-driver kernel; no old disks or application inputs.
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
output="$project/out/source-gpu-guest"
test ! -e "$output"
mkdir -p "$output"
cd "$output"
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
for option in SMP MULTIUSER PRINTK TTY SERIAL_AMBA_PL011 SERIAL_AMBA_PL011_CONSOLE ARM_GIC ARM_GIC_V3 ARM_PSCI_FW ARM_ARCH_TIMER ARCH_VIRT OF BINFMT_ELF BINFMT_SCRIPT PROC_FS SYSFS TMPFS SHMEM FUTEX EPOLL EVENTFD TIMERFD POSIX_TIMERS BLK_DEV_INITRD RD_GZIP DEVTMPFS DEVTMPFS_MOUNT PCI PCI_HOST_GENERIC VIRTIO_MENU VIRTIO_PCI VIRTIO_MMIO DRM DRM_VIRTIO_GPU DRM_VIRTIO_GPU_KMS DMA_SHARED_BUFFER; do
    scripts/config --enable "$option"
done
scripts/config --enable ARM64_4K_PAGES --disable ARM64_16K_PAGES --disable ARM64_64K_PAGES --set-val NR_CPUS 2
scripts/config --disable DEBUG_INFO --disable MODULES --disable SECURITY --disable RANDOMIZE_BASE --disable DRM_FBDEV_EMULATION
make ARCH=arm64 olddefconfig
# Kconfig silently drops options with unmet dependencies. Require the real drivers.
for option in ARM64_4K_PAGES PCI PCI_HOST_GENERIC VIRTIO_PCI VIRTIO_MMIO DRM DRM_VIRTIO_GPU DRM_VIRTIO_GPU_KMS DMA_SHARED_BUFFER DEVTMPFS; do
    test "$(scripts/config --state "$option")" = y || { echo "Required CONFIG_$option not built in" >&2; exit 1; }
done
make ARCH=arm64 -j"$(nproc)" Image
make ARCH=arm64 headers_install INSTALL_HDR_PATH="$output/headers"
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
gcc -static -std=c11 -O2 -Wall -Wextra -Werror -I"$output/headers/include" "$project/Guest/gpu_kernel_probe.c" -o "$output/mpc-gpu-kernel"
python3 "$project/tools/make_gpu_initramfs.py" "$output/linux-6.12.111/arch/arm64/boot/Image" "$output/busybox-1.38.0/busybox" "$output/mpc-abi" "$output/mpc-gpu-kernel" "$output/payload"
python3 "$project/tools/run_gpu_kernel_gate.py" "$output/payload"
mkdir "$output/corresponding-source"
cp "$output/linux-6.12.111.tar.xz" "$output/busybox-1.38.0.tar.bz2" "$output/UPSTREAM-SHA256SUMS" "$output/kernel.config" "$output/busybox.config" "$output/corresponding-source/"
for name in Guest/abi_probe.c Guest/gpu_kernel_probe.c Guest/init-gpu-kernel tools/build_gpu_guest_gate.sh tools/make_gpu_initramfs.py tools/make_initramfs.py tools/run_gpu_kernel_gate.py tools/run_kernel_gate.py; do
    mkdir -p "$output/corresponding-source/$(dirname "$name")"
    cp "$project/$name" "$output/corresponding-source/$name"
done
cp "$project/../.github/workflows/steamos-gpu-kernel-gate.yml" "$output/corresponding-source/"
cp "$output/linux-6.12.111/COPYING" "$output/corresponding-source/Linux-COPYING"
cp "$output/busybox-1.38.0/LICENSE" "$output/corresponding-source/BusyBox-LICENSE"
tar -czf "$output/GPU-Kernel-Corresponding-Source.tar.gz" -C "$output" corresponding-source
tar -czf "$output/GPU-Kernel-Payload.tar.gz" -C "$output/payload" Image initramfs.cpio.gz payload-receipt.json gpu-kernel-test.json
(cd "$output" && sha256sum GPU-Kernel-*.tar.gz > SHA256SUMS)
