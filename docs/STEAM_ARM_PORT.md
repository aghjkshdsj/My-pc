# ARM64 Linux Steam on iPhone: implementation record

Status: ARM64 Linux boots in CI; new CI jobs are blocked by the account's used-up
Actions minutes. No ARM Steam IPA has been validated or released.
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
This is a Linux-host boot result, not an iPhone result.

2026-09-27: Both Apple framework builds pass, including required exported
symbols. Framework archives preserve symlinks and executable permissions.
The iPhone UI, US keyboard, QMP controls, and streaming/sparse runtime installer
pass compilation and regression tests. The desktop boot test has produced
`MYPC_DESKTOP_READY`, `MYPC_DESKTOP_MOUSE_OK`, `MYPC_DESKTOP_KEYBOARD_OK`, and
`MYPC_DESKTOP_INPUT_OK`. The QMP shutdown gate now passes too.
The same boot, framebuffer, networking, persistence, desktop input and shutdown
tests pass through the embedded Apple framework on macOS (run 36360364471).
Display updates are coalesced to one copy per 33 ms refresh, and idle frames
are skipped. This lowers avoidable memory traffic; it is not a device benchmark.

Valve's actual Steam and steamwebhelper executables pass ELF64/AArch64 checks.
The native client starts its updater and installs its full package set. The
launcher now handles the updater's status-42 restart and scopes a taskset shim
to the helper's CPU-2-through-6 affinity restriction (the VM has two CPUs).
Valve's installed files remain untouched so its integrity check can succeed.
CEF client-window startup is still under test. No account login was attempted.

The release workflow is gated on guest tests, Apple display/boot tests, and
native Steam client-window startup.
An additional release gate launches Steam inside the actual 2 GiB TCG guest,
with the iPhone's initial display dimensions, using a separate disposable disk.
Its IPA embeds the compressed Linux disk,
with an atomic **Set up Steam ARM64** action in the fixed Library entry. The
existing disk is never overwritten. Apple graphics acceleration, audio,
Proton/FEX game execution, and real iPhone testing remain separate open gates.

2026-09-28: Valve's updater now finishes, restarts once, and passes its integrity
check without modifying vendor files. GTK2/SDL2 and VA-API loader dependencies
were added after actual native startup failures. The exact-text X11 keyboard
test passes on Linux. The Apple framework rebuild passed after a transient
source download failure, but the updated Apple boot test could not acquire a
runner because of the account limit. No full Steam window or new IPA has passed
the gates yet.

Native client run 36380641308 now completes the updater and loads CEF and the
login interface. CEF logs report a mapped 700x440 `DesktopLoginWindow` titled
`Sign in to`; the old test only matched `Steam` or `Sign in to Steam` and timed
out. The revised test recognizes this title, requires a mapped full-size X11
window and a live CEF renderer for ten seconds, and prints window/process data
on failure. Five recognition tests pass locally. The complete client probe
still needs a CI rerun; its diagnostic screenshot was not retrievable through
the connector, so visual success is not claimed. No account login was attempted.

An isolated Metal experiment lives in `build/linux-arm-gpu` and
`.github/workflows/steam-arm-gpu.yml`. It builds pinned UTM ANGLE/libepoxy/virgl,
adds Apple's EGL initialization to QEMU's existing headless readback backend,
and requires an actual ANGLE Metal renderer in a macOS context test. It does
not alter the release runtime. Guest 3D rendering and iPhone testing are still
required before integrating this backend. Vulkan/Proton are later stages.

GPU run 36380641380 compiled both iOS and macOS frameworks. The macOS context
reported `ANGLE (Apple Inc., Apple Software Renderer, OpenGL 4.1 APPLE-23.1.1)`
and correctly failed the Metal gate. The experiment now explicitly requests
`EGL_PLATFORM_ANGLE_TYPE_METAL_ANGLE`, using the extension in the pinned ANGLE
and libepoxy sources, instead of accepting the default display backend. It also
records host display hardware. This correction has not been compiled or run
yet; a Mac with available Metal hardware is still required to pass the gate.

Billing checkpoint: the owner reports 2,000/2,000 included Actions minutes used,
0.2/0.5 GB artifact storage used, with the minutes resetting in three days.
Run 36380641594 and its retry failed before runner assignment. Do not keep
retrying until quota or billing is resolved. The standalone client workflow no
longer duplicates the main workflow's reusable client jobs, and the separate GPU
experiment is manual-only. This checkpoint uses `[skip ci]`; after quota is
available, dispatch the main runtime workflow on `codex/steam-arm-linux` at the
latest commit. Rerunning an older run would test the older code. Resume the
experimental graphics workflow separately when its host requirements are met.
