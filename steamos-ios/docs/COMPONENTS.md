# Component coverage record

Archive identity: SHA-256
`74644b0d98e7be56f931ec1d5c1be455f52841e216edef7a3597d9e67f1529e6`;
4,328 entries, **3,672 files**, 166,226,171 expanded bytes, every file CRC passed.
Every file has a group, byte size and SHA-256 in `evidence/archive-files.csv`.
Inventory/dependency scanning is complete; a semantic audit of every line of
vendored gamescope/MangoHud/kernel code is not claimed.

All product integrations below are **planned/unverified on the new phone app**.
Host probe code is implemented separately. No row is marked complete merely
because its source is present.

Implemented bring-up code: separate native host probes, fresh Xcode target,
Linux engine adapter, source-built kernel/initramfs, Linux ABI validator and
guest GL shader diagnostic and a new Vulkan render/readback diagnostic. Hosted
Linux CPU, GL and Vulkan diagnostic/rejection tests passed. Vulkan's two hosted
720p images matched every pixel with zero validation errors; the software driver
was explicitly rejected as acceleration. Native iOS MoltenVK compiled and packaged,
and its unneeded macOS IOKit dependency was removed in a verified rebuild.
Native phone execution is pending. Hosted Venus serialized draws passed through
the external-host SHM branch under an explicit test policy; the unmodified fd
route failed. This is software Linux testing, not a completed guest Metal path.
The source-built CPU engine, recovery and StikDebug adapter are packaged in Linux-gate-9,
alongside a separate native offscreen Vulkan-to-Metal diagnostic. Build 4000008's
phone attempt stopped at its pre-render framework hash check; the signing-compatible
build 4000009 passed compilation/package verification and phone engine identity,
loading and draw return 0. Its missing pixel/GPU receipt prevents graphics acceptance.
Build 4000010 prepares independent structured receipt capture; guest graphics,
moving presentation and gameplay remain unverified.
Official rootfs/index metadata and 35 ARM client package URLs are resolved;
full rootfs/client verification, installation and execution remain open.
Native ARM64 JIT and Linux 6.12.111 boot/ABI checks passed on the actual iPhone
in build 4000007. The recorded kernel-plus-test run took 691.06 ms; it is not
SteamOS startup or gameplay. GPU/Steam/game gates remain open. See `STATUS.md`.

| Archive component | Files | Disposition and dependency | Acceptance |
|---|---:|---|---|
| root-metadata (including hidden files) | 5 | Preserve provenance and license mapping; new build configuration; do not execute embedded directions | All file groups resolve, notices and new target isolation checked |
| image-assembly | 1 | New non-destructive image builder; official Valve RAUC/casync index/chunks/rootfs absent from ZIP | Verify index/provenance, chunks, final image, Linux ABI and rollback |
| scripts | 33 | Audit packaging/Steam/Plasma/apps requirements; write new build integration instead of running image/repartition scripts | Pinned inputs and signed package/checksum checks; no mixed platform stack |
| odin-overlay | 165 | Retain Linux service/session behavior; replace Qualcomm hardware configuration with virtio/iOS device adapters | Detailed service table below, real Game Mode/desktop and OOBE |
| gamescope | 2,304 | Reuse attributed upstream compositor with deliberately scoped virtual-output patches; Vulkan/Wayland/Xwayland needed | Frame-origin/pacing, scaling, rotation, focus, Home/QAM z-order, session switching |
| MangoHud | 416 | Linux ARM and x86 overlay/thunks; native host GPU/thermal metrics supplied through explicit telemetry | Game-only HUD, no global layer on Steam, correct FPS units, preset/hide behavior |
| kernel | 385 | Archive has config/patch/build/payload material, not complete upstream Linux source. SM8550 hardware/ABL/firmware is inapplicable to iPhone app VM | New generic ARM virt kernel source/config; virtio storage/net/input/audio/GPU; no Qualcomm drivers linked |
| Decky | 85 | Loader external, plugins contain hardware assumptions; retain Box64 helper scope and session-owned process tree | Single loader, restart after Steam update, no children survive session; safe host thermal adapter |
| lsfg-vk | 161 | Optional Vulkan layer requires proved bridge/features and separately obtained user-licensed model/assets where needed | Optional generation counter separated from base FPS and latency; not used to meet target |
| MESA-Easy-Manager | 30 | Replace hardware driver-switch operations with compatible pinned guest transport packages; retain configuration UI purpose | Atomic upgrades/rollback without breaking official graphics ABI |
| mesa-sm8550 | 15 | Prebuilt Adreno Turnip/GL/Wayland `.so` files are Linux hardware-specific, not Apple GPU drivers. New Mesa guest virgl/Venus plus native host engines required | Per-library provenance and features; no `libvulkan_freedreno.so` as an Apple driver |
| Proton-ARM-Easy-Manager | 25 | Retain guest Proton version/prefix management; actual Linux Proton and Steam runtime external | Pin selected Proton/FEX/runtime, launch/rollback, per-game config |
| NO_Steam | 10 | Preserve shortcuts, artwork/metadata, explicit user game import and launch compatibility | Create/relaunch shortcut and preserve saves; no credentials in reports |
| ufs-install | 12 | Qualcomm repartition operations cannot apply. Purpose becomes app-sandbox image allocation/resize/import/export | Never repartition phone/PC; capacity/ENOSPC/transaction recovery tested |
| system-fixes | 13 | Keep session/touch/LSFG requirements; AYN Thor dual-screen/DT/sysfs fixes have no iPhone counterpart | iPhone touch, orientation, suspend/foreground restoration; explicit unsupported dual screen |
| BOX64 | 5 | Actual source/binaries fetched externally. Keep explicit helper scope, not FEX global binfmt | Real Decky helper under Linux ARM, one handler, game launch unaffected |
| SteamROMManager | 2 | Placeholder/launch integration; upstream ARM64 Electron/app dependency | ROM discovery/shortcut metadata; user-provided ROMs, no bundled games |
| InputPlumber | 1 | Placeholder only; external ARM build. Input source becomes host GameController/UIKit -> virtio input -> guest evdev/InputPlumber | Physical controller hotplug/buttons/axes/triggers, OSK, haptics and no duplicate devices |
| docs | 4 | Reviewed build/fixes, release, Decky/FEX/Box64 and Discover/Flatpak lessons | Requirements translated into regressions; source claims distinguished from phone evidence |

## Overlay features, services and hardware coverage

| Requirement | Linux side | iOS side / explicit limitation | Test |
|---|---|---|---|
| Game Mode | systemd user session, gamescope, Xwayland, one actual ARM Steam Gamepad UI | Host displays guest output and delivers input | Steam Home/QAM above game, scaling/focus, controller navigation |
| Desktop Mode | Plasma Wayland/KWin, kscreen, SDDM/steamosctl session switch, file manager/Ark/Kate | Same host display/input; no global Game Mode Qt/IBus variables | Repeated switch both ways, no duplicate Steam/loader/keyboard |
| CEF/Steam runtime | ELF ARM binaries, glibc/loader, shared libraries, launcher/SDK wrappers, pressure-vessel and namespaces | CPU engine supplies Linux machine; native host cannot `dlopen` ELF | CEF GPU pixels, sign-in, library, license/depot download and game launch |
| Audio | PipeWire/Pulse/ALSA -> virtio sound or a dedicated guest stream | AVAudioEngine/AVAudioSession, bounded ring/resampling/interruption handling | Stereo/channel/rate correctness, underruns and long-run latency, headphones/interruption |
| Controllers/touch/HID | evdev/uinput/uhid, InputPlumber Deck pad and keyboard, IBus scoped by session | GameController, UIKit touch/text, keyboard/mouse events, supported haptics | No doubled axes/keys, hotplug, OSK handoff, disconnect while held |
| Storage/downloads | ext4 root/home, Steam depot verification and decompression, guest block queues | App-private APFS files, measured queues/cache policy; foreground URLSession only for OS packages | Save integrity, cancel/resume, corrupt chunk repair, measured network/disk/decompress stages |
| Network/Wi-Fi/Bluetooth | virtio-net + user networking/DNS; guest NetworkManager sees virtual NIC | iOS owns actual radio/SSID/connectivity and controller Bluetooth pairing | DNS/reconnect/offline/proxy path; guest cannot claim physical radio control |
| OOBE/time/localization | Steam setup, timezone, offload, home creation | iOS supplies clock/localization/network readiness, app storage capacity | First install distinct from cold launch; no stub update-success claim |
| Updates | coherent SteamOS packages and Steam manifest channel; signed/hashed transactional inputs | New image staging, rollback and independent user data | Power-loss/ENOSPC/corrupt input; stable/beta deliberate and recorded |
| Overlay/QAM/Steam overlay | mangoapp/game focus, Steam overlay libraries including ARM/x86 paths, Decky CEF bridge | Host HUD only shows host metrics, not replacement QAM | Correct z-order, hide on game exit, full SDK overlay paths |
| Plugins/power/LED | guest Decky/Box64 and original plugin UI logic | iOS thermal-state observation and adaptive budgets; arbitrary CPU/GPU clocks, fan and Odin RGB controls unavailable | No fake clock/fan/LED settings; process lifecycle and capabilities |
| Discover/Flatpak | external Flathub/OSTree/apps; namespace/seccomp/FUSE and privilege metadata inside Linux image | No iOS setuid emulation; all guest permissions stay in guest filesystem | Install/launch/uninstall, writable offload, real update errors |
| Lutris/Heroic/ROMs/non-Steam | ARM Linux launcher builds, Python/Electron/Node inputs, game-specific dependencies | Host only runs environment; optional vendor credentials stay guest-local | Auth/download/import/launch individually, additional memory budget |
| Display/dock/HDR | virtual connector, compositor modes, color formats and guest cursor | CAMetalLayer, iOS orientation/external display limits and supported color space | 720p scaling/pacing, rotation, external display only if measured; no invented HDR |
| Suspend/shutdown/battery | orderly guest pause/flush, bounded session teardown | iOS app lifecycle owns suspension; phone power key stays iOS-owned | Background/foreground, storage flush and input release; no multi-minute plugin stop |

External inputs not yet integrated include the full authenticated official
rootfs/chunks and complete Steam ARM runtime/CEF/UI/SDK packages (the index and
35-package stable download plan are resolved; metadata is not installation), Mesa
guest drivers plus Darwin virgl/Venus/ANGLE/MoltenVK, Steam's FEX/x86 rootfs,
Proton/Wine/DXVK/VKD3D/runtime, Box64, InputPlumber/libiio, Decky Loader and plugin
build dependencies, Qt/KDE/Plasma extras, Flatpak/Flathub/FUSE, Heroic/Lutris/SRM,
and owner-licensed game depots. The CPU-only QEMU/iOS engine, its dependencies,
Linux 6.12.111 and BusyBox 1.38.0 are already source-built and packaged with
corresponding source in the disposable Linux gate. Each remaining input needs
a resolved version/source/checksum and
license receipt before redistribution. No game or account data is in the build.
