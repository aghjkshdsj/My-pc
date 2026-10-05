# Component coverage record

Current build25 corrects the missing same-thread RCU retirement in the fresh
QEMU adapter. Its native engine export, device-target iOS build, actual packaged
export, source archive and host symbols pass independent checks. Native TLS
lease tests pass optimized/sanitized execution, alongside all preserved receipt
controls. Device stability/readiness verdicts are kept in the private local
record; no desktop, ARM Steam, mutable transport, game or performance row is
completed by this package. Next implementation is explicit native-reader release
and guest buffer reacquisition; the final source trace verifies the packaged
warning-only timer and identifies the missing native-consumer/guest fence dependency.
See MOVING-OUTPUT-INTEGRATION.md and
[thread retirement](RCU-THREAD-RETIREMENT.md). Owner inputs/results remain only
in the private local record; the original archive/blueprint mapping is preserved.

Historical build24 package checkpoint independently verifies the retired/joined Linux worker,
durable finalization checkpoints, local OS crash-payload storage/export and exact
host dSYM/package UUID. Native iOS Release and all preserved receipt/recovery
boundaries passed. These are package/diagnostic results; phone OS delivery and
the cause/correction of prior termination remain unverified. The current owner
device verdict is kept in the private local coverage record.

The reusable three-buffer ownership component passed optimized/sanitized ARM
source tests and 100,000 content-frame reuses. Native engine/guest release-fence
integration, moving phone output and compositor/WSI are still open. This source
contract closes no SteamOS desktop/Game Mode/client/game feature or performance
row. See GPU-GATE-4000024.md and MUTABLE-FRAME-TRANSPORT.md. Every original
archive/blueprint group and historical checkpoint below remains preserved.


Current build4000023 adds a separate eight-immutable-image Linux producer and
bounded native alias/screen GPU consumer. Source/IPA and corresponding-source
verification passed, with 107 Python and 149 native frame checks plus the
preserved original rejection boundaries. Kernel/ten frameworks are unchanged;
the initramfs adds a separate AArch64 frame binary. This historical package record has no device verdict; owner results remain separate. Actual display timestamps,
continuous output, mutable-buffer synchronization, WSI/compositor, all SteamOS
product families and performance rows remain open. This does not complete a
desktop or game row. See [eight-frame gate](GPU-GATE-4000023.md). Previous entries
below are historical; every archive and DroidDeck mapping is preserved.


Current build4000022 source adds scheduled main-thread Core Animation
presentation, bounded lifecycle evidence and strict schema2 display receipts.
Physical iOS Release, separate native adapter compilation, 98 Python and 100
native screen checks passed. The public IPA and all 14 selected source files
were independently verified; 14 exact Linux/engine files are preserved. Phone
acceptance, moving animation, WSI/compositor and all product/performance rows
remain independent and open. See [current screen gate](GPU-GATE-4000022.md).
Older checkpoints below are historical and retain every archive/blueprint row.

Current screen integration: CAMetalLayer, exact imported-guest texture GPU
sampling, separate drawable/completion callbacks and a bounded two-frame
acceptance join are implemented for build4000021. Actual physical ARM64 iOS
Release compilation, 92 Python checks, 75 native screen checks and independent
public IPA/source verification passed. Phone screen acceptance remains pending. This does not close moving animation,
WSI/compositor, SteamOS sessions, full product features or performance rows.
See [current screen gate](GPU-GATE-4000021.md). Earlier bring-up entries below
are historical checkpoints, preserved with the archive and blueprint mappings.

The owner also selected DroidDeck as the functional blueprint. Its separate
inventory accounts for **735 files**, 883 ZIP entries and 52,717,893 expanded
bytes, with every file CRC checked. SHA-256:
`d55ebf34a488cd15b34eb523e4bca16ae7a96b970e02cfa26d53b1f1fdc1009b`.
The [DroidDeck mapping](DROIDDECK-BLUEPRINT.md) covers all product families,
external dependencies, Android mechanisms and iOS acceptance work. See
`evidence/droiddeck-summary.json` and `evidence/droiddeck-files.csv`; signing
inputs are counted with names/digests withheld. Android source and binaries
remain reference material outside the Xcode target. The original SM8550
inventory below remains intact. No row becomes complete from blueprint reuse.

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
Native phone GPU/pixel acceptance passed in build 4000010, with all 1,843,200
checked pixels correct on Apple A17 Pro GPU. This is offscreen host execution. Hosted Venus serialized draws passed through
the external-host SHM branch under an explicit test policy; the unmodified fd
route failed. This is software Linux testing, not a completed guest Metal path.
The source-built CPU engine, recovery and StikDebug adapter are packaged in Linux-gate-10,
alongside a separate native offscreen Vulkan-to-Metal diagnostic. Build 4000008's
phone attempt stopped at its pre-render framework hash check; the signing-compatible
build 4000009 passed compilation/package verification and phone engine identity,
loading and draw return 0. Its missing pixel/GPU receipt prevents graphics acceptance.
Build 4000010 implements independently verified structured receipt capture and
passed its separate physical phone offscreen gate. The native iOS Venus renderer
compiled and passed iOS platform/API/dependency checks in run 37064765557;
actual phone loader/shared-memory/guest integration remain open. Guest graphics,
moving presentation and gameplay remain unverified.
The new separate graphics kernel passed real hosted ARM virtio-GPU allocation,
mapping, transfer ioctl and cleanup, including rejection with the device removed
(run 37067848259). It is a 2D driver test and does not establish host pixels,
guest shader acceleration. ANGLE and the EGL-enabled QEMU bridge now compile
and are packaged in build 4000012. Its physical-phone report passes Linux ABI
and the virtio-GPU allocation/map/CPU-pattern/transfer-ioctl test, then fails
guest Vulkan initialization at shared-resource creation. No physical guest
shader result is claimed.
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

## Current native immutable-resource coverage

Build 4000020 reserves one bounded diagnostic readback for each distinct immutable
Linux export resource. Reinstallations are tracked by generation/lifecycle while
unchanged repeated resources do not spend another readback. Changed format,
layout, crop or orientation is rejected. Native/Python acceptance requires every
installation's flush/disable sequence, both distinct phases/resources at their
first flush, exact native device/layout/pixels/fences and guest cleanup.

Actual budget fixtures, 56 native image checks, 87 Python checks and physical iOS
Release compilation passed. Independent source/IPA verification passed; all 15
changed source files match and the full guest/engine closure is byte-identical to
verified build19. Its BGRA/XRGB format and real pinned-kernel framebuffer controls
are retained. These hosted checks cannot establish a new phone import pass.
Phone image import, visible presentation and all SteamOS/client/game component
acceptances remain open. See GPU-GATE-4000020.md and its public package-only
receipt. Private owner results remain excluded. Earlier bring-up paragraphs below
are historical checkpoints; original archive/DroidDeck feature mappings remain.

## Overlay features, services and hardware coverage

Build 4000017 implements a separate Linux image producer, native engine ABI,
retained Metal texture consumer and strict guest/native receipt join. It passed
physical ARM64 iOS compilation, 73 Python checks, 28 guest receipt checks,
27 completion-ledger checks, 33 image-receipt checks and package verification.
The next guest source corrects the export query to explicit DRM modifier tiling;
actual ARM compilation, native query rejection fixtures, missing-device/2D-only
boots and software-renderer rejection passed in run 37218376178. Native receipt
checks now reject wrong/missing modifier metadata (37 checks).

| New coverage task | Source/build state | Device/product state |
|---|---|---|
| Linux image export format | Explicit modifier query and matching creation, returned modifier and memory-plane layout checks compiled | Actual supported image export still requires a fresh device result |
| Guest/native image transport | Versioned resource/generation/ownership callback and retained native alias consumer implemented | Both image phases, fences and release must pass on the phone |
| Visible Metal presentation | Contract and source boundary documented | CAMetalLayer moving presenter, pacing, lifecycle and resize unfinished |
| Full product components | Existing archive and DroidDeck mapping retained below | SteamOS/client/desktop/Game Mode/FEX/Proton/input/audio/downloads/plugins/game targets remain open |

Actual owner records remain in ignored local `evidence/device/`. These source
checks do not close any unverified device or product row. See
[current export/import diagnostic](GPU-GATE-4000018.md) and [presentation acceptance](PRESENTATION-GATE.md).

Build 4000016 passed 63 Python evidence tests, 28 native guest receipt checks,
27 production ledger checks, native recovery/capture fixtures, physical ARM64 iOS
Release compilation and independent public IPA/source verification. Known JSON
receipts have a bounded 512 KiB allowance; plain logs retain 128 KiB tails.
Zero-duration observations cannot replace required timed GPU work. This closes
diagnostic source/build tasks only. Current device acceptance remains in the
local coverage record; image import, moving presentation and full product rows
remain open. See [preserved recovery package](GPU-GATE-4000016.md) and the existing native
scanout boundary/next acceptance sequence in [the presentation gate](PRESENTATION-GATE.md).

Build 4000015 adds a separately source-built MoltenVK observer for actual guest
command-buffer completions, with no added GPU workload. Native callback/lifetime
fixtures, 25 production ledger rejection checks, 62 evidence tests, Release iOS
compilation, recovery tests and independent IPA/source verification passed.
This completes a source/build diagnostic task; device acceptance is recorded
separately. Import, moving presentation and all full product
component rows remain open. Device acceptance records are retained separately
and locally. See [observer build](GPU-GATE-4000015.md).

Historical build 4000014 adds an app-private renderer communication-file adapter
and preserves the corrected Linux Mesa/Venus payload. Actual native Darwin file
tests, integrated physical ARM64 iOS compilation, recovery/report tests and
independent public IPA/source verification passed. This closes a source/build
task within the graphics row, not the row's phone acceptance. Private allocation,
guest shaders, independent Metal completion/import, moving output and the full
Steam/game sessions require new device evidence. All component acceptance rows
below remain open. See [build details](GPU-GATE-4000014.md).

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


Graphics implementation now includes a separately source-built GPU-capable guest
kernel with hosted 2D DRM allocation/map/transfer and missing-device rejection,
plus Mesa 26.2.2 ARM Linux virgl/Venus libraries and an isolated missing-GPU
rejection in run 37074804870. These do not close the GPU/compositor rows: no
phone guest shader, host memory-import, moving presentation or Steam/game result
exists yet. Native ANGLE ARM64 iOS compilation passed in run 37075043878; the
explicit dynamic framework-loader correction also passed run 37077105285. The separate
EGL/Metal QEMU adapter and full EGL/Venus renderer passed physical-iOS builds
37078645613 and 37078312649. The complete disposable Linux graphics initramfs
passed build 37079133580, including exact loader/DSO dependency resolution and
package corresponding-source closure. Real ARM Linux boots retained ABI success
and correctly rejected both missing-3D controls. Phone build 4000011 passed
actual Release compilation, native receipt/recovery tests and independent public
package verification. It packages this diagnostic payload and the audited native
engine closure. Positive
phone guest Vulkan pixels, independent host Metal completion/memory import,
moving presentation and the full SteamOS image remain open. No product component
row or performance target becomes complete from compilation or negative controls.

The 4000011 phone attempt subsequently exited before Linux boot because the
headless backend was omitted with Pixman disabled. The corrected engine passed
run 37092127907 and build 4000012 passed Release/recovery/receipt tests and
independent ten-framework IPA verification. The fresh host checks real backend
registration before boot. This fixes a display dependency/export packaging
problem; the GPU/compositor rows remain open until positive phone guest rendering,
host completion/import and moving presentation are demonstrated.

The subsequent fresh build 4000012 report matches the exact IPA, payload and all
ten engine code sections. Linux ABI and the virtio-GPU DRM memory check passed
on iPhone16,2 / iOS 27.0.1 build 24A446. Guest shaders remain unverified:
RESOURCE_CREATE_BLOB failed with ERR_UNSPEC, followed by invalid-resource errors,
and vkCreateInstance returned -1. The diagnostic shut down normally. The normal
report lacks host engine output; saved diagnostic logs are required to distinguish
the remaining allocation/renderer/resource-metadata branches. Sanitized receipt:
`evidence/primary/ios-guest-vulkan-4000012-partial.json`. No complete SteamOS,
compositor, game or performance acceptance changes from this partial result.
