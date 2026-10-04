# DroidDeck blueprint for the fresh SteamOS iPhone project

The owner selected `DroidDeck-main.zip` as the functional blueprint. Its source
and documents are reference data, not instructions to execute its scripts.
The archive is preserved; its reference extraction lives only in ignored
`upstream/DroidDeck-reference`. No Android app, signing input, binary, artwork
or previous iOS application has been imported into the fresh host target.
`evidence/droiddeck-summary.json` and `evidence/droiddeck-files.csv` account for
all files, including withheld signing inputs. File inventory is complete;
a semantic review of every vendored line is not claimed. The archive hash pins
this reference; a matching upstream commit has not been established.

## The central platform difference

DroidDeck's `runtime/LinuxRuntime.java` constructs a PRoot command for a glibc
ARM64 filesystem. `session/SessionService.kt` launches its Linux session script,
gamescope and the real ARM Steam client. Games run through Linux ARM64 Proton
and its FEX helpers. The Android host already supplies a Linux kernel.
[PRoot](https://proot-me.github.io/) translates Linux paths and selected Linux
system calls using Linux ptrace; it does not supply a Linux kernel or translate
Linux system calls into Darwin calls. This is Linux userspace compatibility on
Android, rather than hardware virtualization or a full-system CPU emulator.

Its graphics path uses Linux Turnip/Adreno KGSL, an Android Wayland compositor,
AHardwareBuffer allocations, dma-buf fences and SurfaceControl presentation.
`waylandcomp/src/ahb_swapchain.c` retains and releases game buffers against
display fences. The [Android NDK buffer API](https://developer.android.com/ndk/reference/group/a-hardware-buffer)
defines this Android memory sharing mechanism. None of these handles is an
Apple Metal texture. Renaming that API would not produce a working iOS bridge.

The requested implementation remains an actual ARM Linux/SteamOS environment
with a new native ARM64 iOS host. The currently exercised Linux execution engine
is QEMU TCG software system emulation. StikDebug enables executable code for JIT;
it does not supply EL2 hardware virtualization. FEX translates x86 game code
inside Linux; Proton implements Windows APIs. Those are distinct layers.
Hardware acceleration of guest graphics still requires proving the Linux
virtio-GPU/Venus or virgl route through native MoltenVK/ANGLE to Metal.
Linux boot and separate native Metal shader results do not prove that route.

DroidDeck's smaller Android-adapted Linux runtime and LXQt/labwc desktop do not
replace the requested Valve SteamOS rootfs and Plasma desktop. Adopting that
different distribution or replacing the Linux kernel with a Darwin syscall
compatibility layer would require the owner's agreement. This blueprint adopts
the useful behavior and lifecycle design without making that substitution.

## Product behavior to carry forward

The eventual launcher should offer Steam, Games, Desktop, optional Store,
Components, Setup and Updates, with controller navigation and a persistent
Resume entry. Steam is the real client in Game Mode, not a simulated library.
Setup reports actual runtime/JIT/graphics readiness and gives a concrete repair
action. Play becomes available only when the installed runtime can start.
Stopping a session asks before ending a running game, shuts down Steam cleanly
and preserves caches, prefixes and saves. Diagnostic controls remain visibly
separate from playable sessions until the execution and presentation gates pass.

The Android source paths below are relative to the reference archive. Each row
specifies iOS work and acceptance; **no product row is complete on the phone**.

| Component | DroidDeck source evidence | Fresh iOS implementation and acceptance |
|---|---|---|
| Linux runtime and setup | `runtime/LinuxRuntime.java`, `runtime/LinuxRuntimeInstaller.java`, `ui/FrontEndSetup.kt` | Verified Valve rootfs image, dedicated writable home/game storage, native setup state. Validate package/image provenance, Linux ABI and interrupted install recovery. PRoot's Android host launch cannot be copied. |
| Game Mode / Steam ARM | `tools/linuxfs/overlay/usr/local/bin/bannerlator-session`, `tools/linuxfs/overlay/usr/local/bin/bannerlator-steam-install`, `tools/linuxfs/overlay/usr/local/bin/bannerlator-steam-launch` | Real Valve ARM client/CEF in Linux gamescope; verify sign-in, library, offline launch, QAM/Home overlays, clean exit and time to usable Steam. Keep credentials out of diagnostic exports. |
| Desktop | `tools/linuxfs/desktop/droiddeck-desktop`, `runtime/DesktopCatalog.kt` | Keep requested SteamOS Plasma/KWin and session switching. Validate desktop input, clipboard, windows and return to Steam. DroidDeck's LXQt/labwc fallback is reference behavior, not an adopted desktop replacement. |
| FEX / Proton / DXVK / VKD3D | `session/ComponentsManager.kt`, `session/ProtonExtras.kt`, `core/FexPreset.kt` | Pinned Linux ARM Proton and compatible FEX helpers, x86 runtime where needed, owned per-game prefixes and environment. Test a translated CPU program before a real game. Preserve correct memory ordering and self-modifying-code behavior; aggressive presets need per-game evidence. |
| Guest graphics and driver pairs | `gpu/LinuxVulkanDriver.java`, `ui/GpuDriversPanel.kt`, `cpp/adrenotools/` | Match Linux Mesa virgl/Venus with the exact native ANGLE/MoltenVK renderer and rollback metadata. Prove non-software device, guest shader pixels, host completion and then presentation. Turnip binaries and `/dev/kgsl-3d0` are inapplicable to Apple GPUs. |
| Compositor and presentation | `wayland/CompositorHost.kt`, `cpp/waylandcomp/src/{compositor,ahb_swapchain,sc_layer,vk_present}.c` | Guest gamescope/Wayland/Xwayland and explicit host texture ownership, synchronization and paced CAMetalLayer output. Validate format/tiling, resize, rotation, overlay z-order, release after GPU completion and no stale frames. No claimed zero-copy before a measured import. |
| Frame pacing and scaling | `session/SessionPrefs.kt`, `cpp/waylandcomp/src/effects_chain.c`, `cpp/shaders/` | Bounded buffers/in-flight work, display-linked cadence, per-mode render resolution/cap, optional Metal scaling. Count guest-rendered and displayed frames separately; measure p50/p95/p99 intervals and input latency. Start at 1280x720. |
| Optional frame generation / HDR | `cpp/framegen/`, `gpu/FrameGen.kt`, `gpu/Lossless.kt`, `wayland/HdrSupport.kt` | Feature/capability and asset-license gates, actual HDR/color verification and separate generated-frame counters. User-owned Lossless Scaling inputs are external. Never use generated frames to satisfy the 60-80 base FPS target. |
| Physical controllers and Steam Input | `input/PadBridge.java`, `session/SteamDeckPad.kt`, `session/RumbleComponent.kt` | GameController/CoreMotion host events into Linux virtual input devices; Deck or Xbox semantics, gyro, QAM/Home, hotplug, remapping and rumble. Verify axis/dead-zone/button ordering with Steam and a game. |
| Touch / keyboard / clipboard | `input/OnScreenControls.kt`, `input/KeyboardHost.kt`, `input/PointerGestures.kt`, `input/SessionClipboard.kt`, `cpp/waylandcomp/src/wl_text_input.c` | Native touch/trackpad/keyboard and clipboard adapters into the real guest session. Verify text entry, focus, drag/scroll, rotation and profile persistence. |
| Audio and microphone | `audio/PulseAudioComponent.java`, `audio/DirectAudioRelayComponent.java`, `tools/aaudio-sink/`, `assets/directaudio/` | Guest PulseAudio/PipeWire or virtio audio to a bounded native Core Audio/AVAudioSession ring. Measure latency, underruns, Bluetooth/device routing and interruption recovery; microphone opt-in. AAudio and shipped Android ELF sinks cannot load on iOS. |
| Network and downloads | `core/Downloader.java`, `runtime/LinuxNetworkLinkComponent.kt`, `tools/linuxfs/overlay/usr/local/bin/bannerlator-netmanager` | Guest virtual networking plus native resumable runtime downloads; streaming disk writes, checked content ranges/identity, signed manifests where available and hashes before activation. Verify reconnect, changed server content, cancellation, ENOSPC, Steam downloads and throughput on the phone. |
| Library, imports and saves | `frontend/AddedGames.kt`, `session/{GameStorage,SecondaryLibrary,GameSaves}.kt`, `tools/linuxfs/overlay/usr/local/bin/bannerlator-steam-library` | Explicit user-selected import, Steam metadata preservation, scoped host file access and guest storage. Transactional save export/import and no overwrite of old projects/disks. Verify a real game remains installed after restart. |
| Per-game configuration | `core/GameEnvironment.kt`, `session/GameEnvironmentStore.kt`, `ui/GameEnvironmentEditor.kt` | Versioned per-game launch options, resolution and compatible Proton/FEX settings with safe defaults and rollback. Verify environment precedence and no leakage between games. |
| Performance overlays | `tools/mangoapp/`, `session/{CpuStat,GpuStats,GpuMem,Hwmon,Battery}Component.kt` | Linux MangoHud/mangoapp with explicit host telemetry. Distinguish CPU emulation, guest work, Metal completion, base FPS and display FPS. Use public iOS thermal/memory APIs; unavailable Android clocks/sysfs counters remain unavailable. |
| Decky and plugins | `runtime/DeckyManager.kt`, `DeckyMenu.kt`, session supervision | Pinned ARM loader in Linux, session-owned supervision and compatibility review per plugin. Verify restart after Steam updates and no orphan processes. Qualcomm hardware plugins need new host adapters; arbitrary plugin availability is unverified. |
| Linux apps / emulators / Store | `runtime/{FlatpakManager,BwrapSpawner,AppImageManager,UserApps}.kt`, `store/` | Optional ARM Linux applications in the same guest, with real namespace/portal support and GPU transport. Avoid copying Android's fake-bwrap or browser-sandbox bypass as a default. Verify packages, AppImage extraction, launches and data retention. Full dependency closure remains external. |
| Session lifecycle and recovery | `session/{SessionService,OrphanReaper,SessionSuspendController,SessionArtifacts,CrashHandler}.kt` | Session-owned Linux process tree, foreground/background lifecycle, durable pending-test journal and share-on-reopen recovery. Native recovery capture is implemented; full Steam/game suspend/resume and graceful shutdown still need device tests. |
| Updates and rollback | `update/{AppUpdates,SelfInstaller}.kt`, `tools/release/`, `ui/UpdatesPage.kt` | Checked component/runtime updates, staged activation and rollback, preserving user data. IPA delivery currently uses verified GitHub prereleases plus iLoader. Android APK self-install and wireless ADB fixes have no direct iOS implementation. |
| Terminal / diagnostics | `session/SessionTerminal.kt`, `cpp/termux/`, `core/{DeviceReport,LogRedactor}.kt` | Real guest console, bounded native/guest logs and explicit owner sharing. No remote debug provider or external control socket enabled by default. Build 4000013 adds the host log tail to the normal report. |
| External display / second screen | `ui/SecondScreenPresentation.kt`, `input/SecondScreenMode.kt` | iOS external-display capability check and optional second view/trackpad after the primary presenter works. Android dual-screen presentation is not assumed available. |
| UI, accessibility and localization | `ui/`, `app/src/main/res/`, `artwork/` | Fresh SwiftUI/controller-first flows, readable readiness/results, accessibility and localized strings. Treat artwork as reference; ship independently created assets with known licenses. Do not display unimplemented features as working. |

## Missing external inputs and source obligations

The ZIP does not contain a complete SteamOS rootfs, Valve Steam/CEF downloads,
all Proton/FEX/Steam Linux Runtime packages, game content, every Flathub runtime
or complete corresponding source for its prebuilt Linux/Android libraries.
`runtime/LinuxRuntimeInstaller.java` resolves an external `linuxfs.json` catalog in
`The412Banner/winlator-contents`; Steam's install script fetches Valve packages.
Gamescope, wlroots, PRoot/talloc, PulseAudio and synchronization pack recipes
also resolve upstream sources. Catalog URLs do not establish a verified image
or a reproducible package closure. No Android runtime is installed by this audit.

For iOS, keep the existing Valve package/rootfs inventory and pin the full
Linux userland/graphics dependency closure before installing it. Real games
must come from the owner's legitimate library. Hollow Knight is not bundled.
The full rootfs and runtime footprint must be budgeted independently of the
small diagnostic initramfs; its current RAM allocation is not a Steam memory
budget. Linux GL and Vulkan paths both need coverage, including CEF and gamescope.

[DroidDeck's repository](https://github.com/Droid-Deck/DroidDeck) identifies the
app as GPL-3.0 and credits WinNative/Bannerlator for runtime/input work. Its
per-file third-party notices also apply. This change uses a functional blueprint
and new mapping documents; it does not copy app implementation into the MIT host.
If an implementation is ported or linked later, retain attribution and determine
the resulting GPL and corresponding-source obligations before distribution;
renaming Kotlin or translating it to Swift does not make it MIT code. Reuse of
QEMU/Linux/BusyBox, Mesa/virgl, ANGLE, MoltenVK, Proton/FEX and runtime packages
continues under their actual licenses and existing source-distribution records.
Bundled shaders, commercial LSFG inputs and artwork need separate provenance.

## Performance lessons and implementation order

`docs/development/proot-performance.md` reports that Android path/process traps
can serialize startup, while selected GPU submits and futex operations avoid
PRoot interception. Its in-process path fast path checks equivalence before
bypassing the tracer. Carry forward the principles: avoid extra translation
layers, repeated filesystem metadata work, excessive wakeups and global locks;
preserve correctness when adding fast paths. Those Android microbenchmarks and
release startup figures are not iPhone measurements and do not predict TCG/FEX
game speed. A Linux kernel running under TCG remains a material CPU cost.

The compositor reference contributes a second important principle: allocate
display-compatible buffers early, retain ownership until the display releases
them, and make acquisition/release fences explicit. The actual Apple bridge
must prove those properties independently. Full-frame CPU readback is limited
to correctness tests; the game presenter needs bounded GPU work and direct
texture presentation. Android GPU clock pinning and scheduler/sysfs controls
are not iOS performance features. Measure sustained thermals and adapt resolution
or frame cap using real data instead of a promised fixed clock.

1. The observer in [build 4000015](GPU-GATE-4000015.md) passed native ABI fixtures,
   integrated ARM64 iOS Release builds, recovery/report/ledger rejection checks
   and independent public IPA/source verification. Obtain fresh guest pixels
   and native Metal completion receipts from the same phone run. The corrected
   DRM request, app-private communication files and allocator/context logs remain;
   native completion does not establish memory import, presentation or gameplay.
2. [Build 4000016](GPU-GATE-4000016.md) preserves complete bounded recovery receipts
   and the exact observer/guest engines. Keep current per-device acceptance in
   the separate local record. Follow the [native image-import/presentation gate](PRESENTATION-GATE.md)
   through layout, alias pixels, fences and resource ownership. Exercise Linux
   GL as well as Vulkan.
3. Implement and measure the moving Metal presenter, resource lifetime, pacing,
   resize, overlays and bounded memory before a desktop/Steam performance claim.
4. Assemble the verified SteamOS image and dependencies non-destructively; bring
   up Game Mode/Steam ARM/CEF, desktop mode, input, audio, network and downloads.
5. Bring up Linux Proton/FEX with CPU and graphics checks; test owned Hollow
   Knight at 1280x720. Measure cold/warm usable Steam startup separately from
   install/download time, base rendered FPS, frame intervals, memory, storage,
   battery/thermal state and a sustained run. Targets remain Steam under 60 s
   and Hollow Knight 60-80 base rendered FPS; neither is verified.
6. Complete plugins, optional Store/apps, HDR/frame generation, external display
   and safe update/rollback using the same component acceptance record.

The blueprint audit expands the work plan. It does not complete the SteamOS
product, establish accelerated Linux graphics or change the agreed architecture.
