# Architecture and proof gates — 2026-10-02

## Decision and limits

Retain the requested Linux-kernel/SteamOS architecture. Build a new ARM64 iOS
host with explicit engine adapters, lifecycle ownership and Metal presentation.
No alternative OS architecture has been adopted. Hardware virtualization,
software system emulation and Linux userspace compatibility are distinct:

| Path | Execution and ABI | Current evidence | Decision |
|---|---|---|---|
| Hardware Linux VM | ARM instructions execute as a guest under EL2; Linux implements ELF, syscalls, processes, futex, signals and IPC | Apple's current documentation metadata lists **macOS only** for Hypervisor and Virtualization. Ordinary sideloaded UTM lists no hypervisor. No valid iPhone entitlement/API path has been demonstrated | Unavailable through the documented public iOS API. Do not infer availability from the A17 Pro ISA, StikDebug or Memory+ |
| QEMU TCG Linux machine | ARM64 iOS engine dynamically translates the guest ARM CPU, MMU and privileged instructions. Guest Linux supplies the ABI. FEX then translates x86 games to guest ARM, itself executed through TCG | Previous app/reference reports establish this class of path, not a new phone result. A new minimal Linux-kernel probe is required | The available Linux-kernel route to test. **Software emulation**, even when guest and host are ARM64. Performance risk is high |
| Linux userspace compatibility runtime | Native ARM instruction execution would still need an ELF loader, Linux ABI and memory model, signal/exception and syscall interception, process isolation and Linux services on Darwin | No such complete runtime has been demonstrated for the proprietary ARM Steam/CEF process tree here. FEXCore alone does not supply it | Research option only; adopting it requires the owner's agreement |
| Bare-metal Linux on iPhone | Replace/boot another kernel and provide Apple GPU/device drivers | No supported path established; outside the authorized app installation scope | Not implemented |

Primary evidence: [Apple Hypervisor](https://developer.apple.com/documentation/hypervisor),
[Apple Virtualization](https://developer.apple.com/documentation/virtualization),
[UTM iOS installation](https://docs.getutm.app/installation/ios/),
[QEMU accelerator documentation](https://www.qemu.org/docs/master/system/introduction.html).
The bounded primary receipts include Apple's JSON platform fields, HTTP status,
retrieval time and SHA-256. Absence of a documented API is not proof that every
private exploit or future iOS version is impossible; none is an established
execution path for this phone and signing setup.

## Fresh host boundary

The host owns one environment session and a new app sandbox. Its eventual
modules are `SessionCoordinator` (single engine owner/state machine),
`LinuxEngineAdapter` (CPU/machine only), `GuestControl` (bounded framed messages,
nonces, no replay of launch), `MetalPresenter` (display pacing and resource
ownership), `InputBridge`, `AudioBridge`, `ImageStore` and `Measurements`.
Swift owns UI/lifecycle; ARM64 C/C++/Objective-C++ own latency-sensitive adapters.
Release optimization is validated at the OS/runtime boundary before enabling
aggressive allocator/VA changes. The published CPU-gate target includes a new
`LinuxGate.mm` adapter and four source-built engine/dependency frameworks. It
loads QEMU's library entry points on a dedicated thread, boots a checked fresh
kernel/initramfs and verifies a new guest nonce/ABI/checksum receipt. Host and
guest diagnostics compile/test separately. Other session/graphics/input/audio
modules remain design boundaries, not claimed implementations.

Linux-gate-2 has been independently downloaded and checked for ARM64 physical
iOS, all framework dependencies, payload hashes and complete ZIP CRC. Hosted
Linux kernel checks passed; no phone receipt has been received. It has no
SteamOS image, Steam/FEX, persistent disk, networking or guest GPU. This gate
does not close the requested environment or performance requirements.

The machine uses an upstream generic ARM `virt` kernel and virtio devices, not
the archive's SM8550 device tree, ABL or Qualcomm kernel. Once CPU/graphics gates
pass, reconstruct a provenance-checked official SteamOS ARM userspace in a new
image. Keep guest kernel ABI and official glibc/Qt/Wayland/platform libraries
coherent. Never copy arbitrary Ubuntu shared libraries into it. Store writable
home/game data separately, preserve Linux permissions/symlinks inside the image,
and perform transactional updates with explicit rollback. Never attach an old
user disk writable during bring-up.

Linux provides the ELF interpreter and `execve`, fork/clone, threads/TLS, futex,
signals, epoll, procfs/sysfs, DBus, namespaces and systemd. FEX uses its Linux
frontend and x86 rootfs inside this Linux environment. The Linux guest should
initially use 4 KiB pages; record iOS's actual page size separately. A Darwin
16 KiB page cannot implement all 4 KiB Linux `mmap`/`mprotect` semantics by
renaming APIs. The Madeira ARM64EC fork targets a different ABI and is reviewed
as evidence, not imported as the implementation.

## Complete proposed graphics paths

```text
Linux x86 game -> FEX -> ARM Linux GL/EGL thunks -> Mesa virgl
  -> guest virtio-gpu -> QEMU/virglrenderer -> ANGLE Metal
  -> shared IOSurface/Metal texture -> paced CAMetalLayer -> phone display

Windows x86/x64 game -> FEX + Linux Proton/Wine -> DXVK or VKD3D-Proton
  -> ARM Linux Vulkan -> Mesa Venus -> virtio-gpu blob/context/rings
  -> Darwin-capable Venus renderer -> MoltenVK -> Metal texture/presentation

Steam ARM/CEF + Game Mode gamescope + Plasma/KWin
  -> their Linux GL/Vulkan/Wayland paths -> the same proven GPU transports
```

The OpenGL path has precedent in the old reference. Its GPU shader/readback
checks do not establish desktop GL completeness, gamescope Vulkan, Proton
compatibility, Hollow Knight frames or a new host implementation. No silent
llvmpipe/softpipe/SwiftShader fallback may pass the accelerated gate.

Standard [Mesa Venus](https://docs.mesa3d.org/drivers/venus.html) requires
external-memory and virtio blob/context support and makes host-visible-memory
assumptions. [MoltenVK](https://github.com/KhronosGroup/MoltenVK) provides Vulkan
portability over Metal on iOS; a Vulkan version number does not establish every
DXVK/gamescope feature or transport compatibility. Guest DMA-BUFs cannot be
treated as iOS IOSurfaces without a mapping/synchronization bridge.

New evidence matters: current pinned UTM virglrenderer includes an external-host
memory path that emulates DMA-BUF transport. Its `vkr_physical_device.c` derives
`is_dma_buf_emulated` from `VK_EXT_external_memory_host`, and its
`vkr_device_memory.c` allocates shared memory for it. Evaluate this **existing
upstream implementation** before inventing a second protocol. Shared pointer
alignment/lifetime, guest mapping under TCG, format/tiling, coherency, fences,
resource destruction and scanout must pass on iOS. Code availability is not a
successful phone test. UTM's older Graphics.md is stale relative to its 2026
build source/release announcement; do not use it to assert Venus is absent.

Neptune forwards D3D commands through virtio to native DXMT/D3DMetal backends;
it is a separate Windows-game transport, not a substitute for the Vulkan
compositor or all Linux graphics. Its current build integration is primarily
documented for macOS. Apple D3DMetal/Rosetta is not an established iPhone path.
[KosmicKrisp's current primary documentation](https://docs.mesa3d.org/drivers/kosmickrisp.html)
explicitly says iOS support is absent; macOS conformance cannot satisfy this gate.

[Gamescope](https://github.com/ValveSoftware/gamescope) needs Vulkan composition,
Wayland/Xwayland, buffer import and display/focus protocols. Use a virtual display
backend in the guest and a native host presentation adapter. Retain actual
gamescope and QAM/session semantics; a Weston screen or Swift menu alone does
not satisfy Game Mode. KWin/Plasma is a separate tested session.

## Ordered milestones and acceptance

1. **Physical host gate:** compile the new IPA; iLoader sign; test StikDebug JIT,
   actual model/build/pages/memory; GPU computation/readback and storage. This
   is preparatory and cannot mark Linux/graphics requirements complete.
2. **Linux CPU gate:** embed a source-pinned engine in the new host, boot a fresh
   minimal ARM Linux initramfs, collect kernel and ELF architecture, fork/exec,
   TLS/pthread/futex, signal, mmap/protection and checksummed CPU results. Compare
   TCG guest wall/process time against native iOS, 1/2/4/6 workers, cooled and
   sustained. Record JIT failure explicitly. A minimal distro is a disposable
   bring-up test, not a replacement for SteamOS.
3. **GPU transport gate:** run Linux ARM and FEX x86 GL *and* Vulkan offscreen
   shader/image tests with patterned readback and shader change; confirm host
   Metal backend and GPU completion. Present moving guest-origin frames with
   source/guest/present counters, resize, sync/destruction, and no CPU full-frame
   readback in the steady state. Measure command/transport/fence/present time.
   Fail on software fallback or unsupported Vulkan features; publish the exact
   extension/format/limit inventory.
4. **SteamOS gate:** reconstruct verified official rootfs; boot systemd/DBus,
   actual ARM Steam/CEF, sign-in/library/downloads and required launcher/SDK
   libraries. Pin stable explicitly; resolve the archive stable/beta conflict.
   Complete Game Mode/gamescope/QAM and desktop/Plasma switches. Measure external
   icon-tap-to-interactive time; separate first install from cold/warm launch.
5. **Games/features gate:** install Steam-provided FEX/Proton under Steam's scope,
   validate x86 Linux Hollow Knight first and Windows/Proton separately when
   available. Do not call a native ARM demo an FEX game. Complete audio/input,
   overlays/plugins/Flatpak/vendor launchers; update coverage after each test.
6. **Performance gate:** exact Hollow Knight depot/build/renderer, 1280×720,
   base render counts, frame-time percentiles and at least 20 minutes sustained.
   Target usable Steam <60 s and Hollow Knight 60–80 base FPS. Targets remain
   unverified; generated frames are separate. If CPU emulation prevents them,
   provide reproducible traces and request agreement before architecture change.

Each gate needs a build/source identity, actual device report and reproducible
workload. Build success, a host shader, inherited screenshots or hosted emulation
cannot complete a physical-phone gate. No completion date or FPS guarantee is
supported by the present evidence.
