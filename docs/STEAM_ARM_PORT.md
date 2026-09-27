# ARM64 Linux Steam on iPhone: implementation record

Status: ARM64 Linux boots in CI; no ARM Steam IPA has been validated or released.
The Windows Steam implementation and build 45 remain available.

## Objective

Run Valve's full ARM64 **Linux** Steam client locally inside My-pc on iPhone,
with JIT, persistent downloads, a fixed Library entry, and usable input/display.
Measure performance on a real iPhone before claiming an improvement. Windows
games still need Proton/FEX; an ARM client does not make x86 games native.

## Architecture decision

Use QEMU's ARM64 `virt` machine and TCG JIT, embedded as an iOS framework using
the existing UTM QEMU port. A complete Linux kernel supplies the process,
memory, filesystem, and syscall behavior Steam/CEF require. The initial CPU
backend is emulation, even though guest and host both use ARM64. Do not advertise
it as hardware virtualization or native execution on an iPhone.

Keep this backend separate from Wine/FEX's existing single-process runtime.
Do not run both at once. Linux owns a persistent ext4 disk; no Windows prefix
conversion or destructive migration. Start with software display, then evaluate
UTM's virgl/ANGLE/Metal and Venus/Neptune paths. Booting Linux or uploading an IPA
does not prove Steam works or that graphics are accelerated.

## Milestones and acceptance gates

1. **Runtime build:** pinned UTM/QEMU source; ARM64 iOS frameworks with no host
   library dependencies; portable launcher; successful CI compile.
2. **Linux boot:** Debian ARM64 image; serial boot evidence; DHCP and outbound
   networking; persistent disk checked across two boots; clean shutdown. Run
   on CI first, then through the embedded Apple-platform backend.
3. **iPhone session:** JIT preflight, memory limits, lifecycle, display, touch,
   keyboard, logs, import/update without overwriting user disks. Device boot
   must be recorded separately from macOS and Linux CI boot tests.
4. **Full ARM Steam:** official Valve ARM64 packages, verified checksums and ELF
   architecture; desktop session; login, Steam Guard, store, downloads; fixed
   Library -> Apps entry routed to Linux, with installed games preserved.
5. **Graphics and games:** Metal-backed rendering where supported, audio,
   controller input, ARM64 Proton/FEX, at least one owned game. Record frame
   times, memory, thermals, and model/iOS version. Software rendering is a
   bring-up fallback, not a performance claim.
6. **Release:** build/check a real `.ipa`; publish experimental prerelease with
   checksums, exact commit, required runtime assets, and device-test results.

## Sources and correction to the earlier assessment

The user's winlator-contents commit
`0d94db5ffe72a47f7d16f220714111d79ecc63e6` has BOTH a Windows SteamLite agent and a
full ARM64 Linux Steam path. The earlier assessment overlooked `linuxfs.json`.
Its r9 image contains Arch ARM, gamescope, Xwayland, PulseAudio, and Mesa's
Turnip/KGSL Android driver. The client is downloaded from Valve at first launch.
That Android rootfs/driver cannot run unchanged on iOS. Its setup and library
behavior inform this port; it is not an iOS runtime implementation.

- [Source catalog](https://github.com/aghjkshdsj/winlator-contents/blob/0d94db5ffe72a47f7d16f220714111d79ecc63e6/linuxfs.json)
- [Source launcher](https://github.com/aghjkshdsj/winlator-contents/blob/0d94db5ffe72a47f7d16f220714111d79ecc63e6/desktop/overlay/usr/local/bin/steamdeck-steam)
- [UTM source pin](https://github.com/utmapp/UTM/tree/7eadb056ae0f91d979059544d0ddcd2d5a40be92)
- [QEMU iOS port](https://github.com/utmapp/qemu/releases/tag/v10.0.12-utm)
- [QEMU virt board](https://www.qemu.org/docs/master/system/arm/virt.html)
- [Valve ARM compatibility](https://partner.steamgames.com/doc/steamhardware/steamframe/compatibility)

## Resume record

Branch: `codex/steam-arm-linux`, based on the existing Steam integration branch.
Target: iPhone 15 Pro Max, 8 GB RAM, iOS 27. Initial Steam guest budget: 2 GiB
plus 128 MiB TCG cache. Available system RAM is not an iOS per-app memory limit.
Build scripts and CI live in `build/linux-arm` and
`.github/workflows/steam-arm-linux.yml`. Update this section with actual test
results and the next unresolved failure after each development stage.

2026-09-26: [first Linux boot job](https://github.com/aghjkshdsj/My-pc/actions/runs/36283488715/job/108519714666)
passed on an ARM64 Linux runner using TCG (no KVM). Debian trixie with kernel
6.12.107 booted twice, reached the host HTTP probe, retained a file on ext4,
and shut down cleanly. Runtime artifact approximately 286 MB compressed.
This is a Linux-host boot result, not an iPhone result. Apple framework builds
are still under validation. Next: boot through the exact Apple dylib bridge,
verify framebuffer output, and integrate the iPhone session.
