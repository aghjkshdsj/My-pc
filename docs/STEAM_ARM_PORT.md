# ARM64 Linux Steam on iPhone: implementation record

Status: the full ARM64 Steam login interface passes inside the actual Apple
QEMU framework as well as native Linux. Linux boot, desktop input, iPhone
compilation and IPA validation pass. The experimental
[steam-arm-preview-24 release](https://github.com/aghjkshdsj/My-pc/releases/tag/steam-arm-preview-24)
contains a real unsigned iPhone IPA. The owner reports successful Steam launch
and account login on the target iPhone. Downloads and gaming performance still
need device testing; the owner reports a slow interface with software graphics.

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
records host display hardware and tests the runner's public Metal device API.
Run `36624577775`, commit `eb2629bc4198e442dd0ca9b7966545a773a844c5`,
passed both framework builds and the Metal context gate. The host reports
`ANGLE Metal Renderer: Apple Paravirtual device` and OpenGL ES 3.0. This proves
the hosted Mac is using the Metal API/backend, not physical iPhone performance.
A compile alone is not acceleration evidence.

The next experiment also prepares a fresh, isolated copy of the verified Linux
guest with Mesa's GLES utilities. It selects `virtio-gpu-gl-pci` and
`egl-headless,gl=es`, removes the forced software renderer only in that test,
requires the guest virgl renderer, compiles a GLES 3 triangle shader and checks
its pixel readback. Animated gears must then produce two distinct frames with
their primary colors through the same iPhone framebuffer callback. Blank,
console, truncated and invalid callback buffers cannot pass that check.
Networking, persistent-disk markers and clean shutdown remain required. This
test uses no Steam credentials and does not alter the owner's Linux disk.
The experiment remains outside the released IPA until the graphics gates pass.

Run `36625838256` at `8833fed343edfedd9a4bc68acf0af5126d62f0a0`
passed the host Metal context, guest virgl GLES shader and pixel-readback checks,
but timed out waiting for animated primary-color frames through the app bridge.
The GLX animation's output was discarded, so its cause is not established yet.
The next test uses Mesa's GLES animation, keeps its diagnostic output and reports
callback dimensions, primary-color counts and distinct frame hashes. It also
summarizes the prior controlled, account-free result using fixed labels. GPU
acceleration is not enabled in preview 24 on this incomplete evidence.

Billing checkpoint: the owner reports 2,000/2,000 included Actions minutes used,
0.2/0.5 GB artifact storage used, with the minutes resetting in three days.
Run 36380641594 and its retry failed before runner assignment. Do not keep
retrying until quota or billing is resolved. The standalone client workflow no
longer duplicates the main workflow's reusable client jobs, and the separate GPU
experiment is manual-only. This checkpoint uses `[skip ci]`; after quota is
available, dispatch the main runtime workflow on `codex/steam-arm-linux` at the
latest commit. Rerunning an older run would test the older code. Resume the
experimental graphics workflow separately when its host requirements are met.

Public-repository resume: GitHub's API now reports `private: false`. Standard
`macos-26` and `ubuntu-24.04-arm` runners can supply the build machines without
requiring the owner to have a Mac. New runtime builds first require the native
Steam probe to pass; QEMU also waits for the bridge checks. This avoids building
full runtime artifacts when an earlier prerequisite is already failing. The
Metal experiment remains separate because compiling on a hosted Mac does not
prove hardware graphics acceleration is available.

Run 36436023097 confirms the public repository can start both Mac and Linux
jobs. Bridge/JIT checks and Valve package verification passed. Native Steam
reported a real X11 `Sign in to Steam` window, but its renderer retained the
zygote command line, so the process-name predicate still rejected it. The probe
now enables loopback-only CEF debugging in disposable tests, reads the actual
login page's ready state and visible password-field geometry, and requires that
live response alongside the mapped window for ten seconds. Normal Steam launches
do not enable this debugging endpoint. No credentials are entered or inspected.

Run 36437513433 produced a screenshot that was visually inspected: the full
Steam login form, account-name and password fields, sign-in button and QR panel
are rendered correctly on native ARM Linux. CDP confirms the visible form is an
`about:blank` popup titled `Sign in to Steam`, populated by `SharedJSContext`.
The probe now selects that popup instead of only the background steamloopback
page. This is visual evidence on native Linux, not an iPhone or TCG guest pass.

Run 36472203528 (commit `f640152f58f56ae34aaeef916d5a63147f54835f`)
passed the automated native Steam test: `Sign in to Steam` stayed mapped for
ten seconds, and the live CEF page reported `readyState: complete` with a visible
password input. The official packages passed checksum and AArch64 ELF checks.
The same run passed bridge/JIT, runtime installer and framework checks, plus
Linux boot/network/persistence/shutdown and exact X11 keyboard/mouse tests.
The Apple framework then passed boot, networking, persistence, framebuffer,
exact keyboard/mouse input and shutdown on the same commit.

The first full Steam-in-TCG test downloaded and verified the ARM client but
stopped immediately with SIGILL (exit 132) on the Cortex-A72 CPU model, before
the updater or CEF could start. The VM and all boot tests now use QEMU's
`max,sve=off,sme=off` model to expose newer scalar/NEON instructions without
scalable-vector state. [QEMU documents this CPU configuration](https://www.qemu.org/docs/master/system/arm/cpu-features.html#sve-cpu-property-examples).
This correction needs the full guest test to pass; the precise faulting
instruction has not been identified. IPA packaging remains gated on that test.

Run 36474188567 (commit `454d221766e75043271cef168c2888a8b6ac193f`)
passes native Steam startup, iPhone bridge/JIT and app integration checks, plus
the Linux and Apple-framework boot, network, persistence, exact desktop input
and shutdown tests with the updated CPU model. The owner cancelled the run
while Steam startup inside that guest was still running, before the probe
returned a result. The CPU change has not yet passed full guest Steam startup.
The IPA job was skipped; no ARM IPA was built or published. The owner then
explicitly requested restarting the Steam test and IPA pipeline. Only that job
and its dependent release job were retried, reusing the passed prerequisites.
Saved guest log artifact from the cancelled attempt:
`linux-arm-steam-guest-logs`, ID `10994650532`.

The explicitly requested retry completed the updater and started CEF without
the previous illegal-instruction failure. It did not present a login window.
First download/install used approximately 18 minutes of the 20-minute probe.
The saved diagnostic report counted one segmentation fault, one CEF network
service crash and a helper restart; no kernel OOM was detected. This is a failed
full-guest Steam test, not merely a successful install. Artifact `10996207496`
holds the failed attempt's log. The safe diagnostic run `36505459642` reports
only fixed error counts and readiness booleans, without republishing raw logs.

Run `36506270696`, commit `b3c1388dc2e789ebd4ab68ca638989446bc93dd5`,
moves the full Steam guest gate from Ubuntu's QEMU 8.2 to the pinned QEMU 10.0.12
Apple framework used by this port. Installation and CEF startup have
separate 30-minute and 10-minute limits, with bounded progress reports each
minute; helper restarts do not renew the CEF budget. The guest still must show
a stable mapped window and a live, complete login form. This run passed native
Steam startup, bridge checks and both Apple framework builds; the full guest
test subsequently failed as recorded below.

That Apple-framework Steam run subsequently failed after installation. CEF's
background page was responsive and complete, but no login popup appeared.
The safe diagnostic run `36586449947` counted 223 `lsof: not found` errors and
65 rejected local WebUI connections. There were no recorded SIGILL, SIGSEGV,
CEF network-service crashes, kernel OOMs, DNS errors or certificate errors in
the inspected report. A broad renderer-crash regex initially matched a process
argument; the corrected predicate reports zero renderer crashes.

The guest now includes `lsof`, which Steam uses to identify its local helper
connections. Debian also lists it as a Steam installer dependency. The launcher
fails before downloading if it is missing. The probe now identifies CEF startup
from the live helper process instead of an optional shell-log message. Bounded
process-state diagnostics record only fixed labels and numbers, never arguments
or input values. Run `36586450467`, commit
`ccab0ec62a875a80fa16570d0dcf88442c109194`, tests these corrections. Its native
Steam and package/launcher checks passed. The corrected full guest Steam test
then passed through QEMU 10.0.12's Apple framework: a stable mapped login window
with a responsive, complete CEF login form, followed by clean shutdown. The
first installation and startup took approximately 11 minutes on the CI Mac;
this is not an iPhone performance measurement.

The same run built and published **SomethingPC-SteamARM64.ipa** in release
`steam-arm-preview-23`. The archive contains the ARM64 iPhone app, iOS framework
dependency closure, kernel, initrd, compressed persistent-disk seed and JIT
script. CI downloaded the uploaded release asset, checked its SHA-256 and
compared it byte-for-byte with the built IPA before publishing the prerelease.
Size: 679,723,864 bytes. SHA-256:
`5275a0433c31d4a1dd228aae03f286cc395dee39079fd4b89cf06a8c8fb2b7e2`.
Corresponding runtime source and the checksum file accompany the IPA.

The owner subsequently tested preview 23 on the target iPhone 15 Pro Max
(previously reported iOS 27), supplied desktop screenshots and reported that
Steam launched and account login succeeded. First-install verification appeared
idle for approximately 7–10 minutes before continuing. This is owner-reported
device evidence, separate from the automated Mac test. Downloads, games and
performance measurements remain unverified; the owner reports slow interaction.
The current configuration uses two virtual CPUs through QEMU TCG JIT and
2048 MiB guest RAM. ARM64 client binaries still run inside the emulated Linux
machine; they do not run directly against iOS. Steam graphics use the CPU,
without guest GPU acceleration. Preview 24 removes the session
navigation header, uses a compact bottom control bar and adds an enlarge/fit
control. A visible local cursor follows direct touch, or relative trackpad
motion with tap-to-click. Session options provide right-click, wheel scrolling
and a held-button drag. Zoom switches to trackpad mode and follows the pointer
so cropped desktop edges remain reachable. Ordinary motion is coalesced at the
display cadence; presses and releases are preserved and click transitions have
a 10 ms interval for the guest USB queue.

An optional performance overlay samples the app's cumulative process CPU time
and physical memory footprint once per second, and counts newly presented guest
frames. CPU 100% means one busy host core and can exceed 100%; this is app CPU,
not guest utilization. RAM is app footprint, not guest allocation or all system
memory. Display FPS can be zero for a static desktop and is capped by the
30 Hz display bridge; it is not a game's internal FPS. GPU is explicitly labeled
software, with utilization unavailable rather than a fabricated percentage.
Metric definitions and thermal state are available from the overlay.

Run `36624109003` at `b94dd7d8d029f6aff3ce36b4e8a4ba6da3c89082`
passed installer, native Steam, Linux boot/input, Apple framework display and
full Steam login-interface gates, then built the updated iPhone app and published
preview 24. The uploaded `SomethingPC-SteamARM64.ipa` was downloaded, checksum
verified and compared byte-for-byte before publication. Size: 679,745,211 bytes.
SHA-256: `283d846c818583d85edeaedb7d843273ff6f905a5000d518a044ee02bd5acf5b`.
The new controls and overlay still need device validation; preview 23's owner
login report does not validate this updated UI or establish a speed improvement.

The owner also requested all available CPU cores. The next build replaces the
fixed two-core app launch with an automatic selection based on iOS's available
processor count, normally six on iPhone 15 Pro Max. A persistent startup picker
also permits fewer cores; preferences cannot oversubscribe the available host
count. The monitor shows the actual selected virtual CPU count. QEMU retains
multi-threaded TCG; this is still CPU emulation, not native iOS execution, CPU
pinning or a guarantee of 100% utilization. Memory remains 2048 MiB. The release
pipeline now boots a six-core guest and requires its online CPU count before
boot/input and full Steam startup can pass. Device timing and thermals must be
compared with two-core operation before claiming a speed improvement.

Fresh guest installations also report download and extraction progress.
Updating the app preserves the existing Linux disk and Steam account data;
guest installer-script changes are included in newly installed runtime images.

The owner's additional JIT-free request is being implemented separately in
[draft PR #3](https://github.com/aghjkshdsj/My-pc/pull/3), branch
`codex/steam-arm-interpreter`. It uses the pinned ARM64 threaded interpreter and
an iPhone target with no Wine/FEX, StikDebug or JIT entitlements. The existing
JIT build remains this branch's release path. App Store readiness and interpreter
performance are separate, unverified milestones.

## First device check after an IPA passes the release gates

1. Sideload the release's `.ipa`. Open **Library → Apps → Steam ARM64** and
   **Set up Steam ARM64** with approximately 13 GB free. Keep the app open
   during installation.
2. Enable JIT with the app's StikDebug action, then **Open Steam**. The first
   start downloads the client from Valve and may restart its updater. The
   keyboard button supplies text input; touch controls the guest mouse.
3. First record whether the desktop and Steam login form appear on the target
   iPhone. Then test account login, Steam Guard and a small owned download on
   the device. No account credentials are needed in development logs or CI.
4. Use **Shut down** before closing the session. Restart My-pc before another
   Linux session or switching to Windows. Confirm that the downloaded content
   is still present in Steam after the next boot.

For a failed boot, the serial log is in the app's shared Documents folder at
`LinuxARM/boot.log`, accessible through Files. Record the iPhone model, iOS
version, build commit, and where startup stopped. A Mac CI pass does not
substitute for this device check. GPU, audio and game execution require their
own follow-up tests.
