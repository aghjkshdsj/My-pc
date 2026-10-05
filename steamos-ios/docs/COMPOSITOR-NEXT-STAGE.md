# Ordinary Linux compositor integration after the eight-image phone checkpoint

Checked 2026-10-05. Official wlroots 0.20.2 source was cloned into an isolated
ignored reference directory and resolved to commit
`d783533489e1f75d6886c2ab5c5960090ef268f8`. Its actual renderer/DRM/allocator
build requirements and MIT license were read; this is source inspection, not
a compositor build. This stage extends the requested ARM Linux guest and native
Metal bridge. It is not an architecture substitution. A small upstream Wayland
compositor is an integration control; SteamOS Plasma and gamescope still require
their own actual sessions, dependencies and device tests.

The two build-4000028 phone reports independently verify the bounded eight-image
Vulkan producer → Linux atomic KMS → virtio/Venus → actual native Metal reader
→ positive Linux output fence/page-flip chain and teardown. Optional Vulkan API
validation layers were absent; the former checker incorrectly required them.
Build 4000029 corrects that distinction without changing the engine or payload.
The corrected IPA/source/symbols are independently verified on the PC. The new
build-4000029 device report also passes the strict raw-observation audit and its
app verdict agrees; the saved recovery result matches and has no pending test.
Validation layers remain unavailable. This does not establish production frame
pacing, mutable-buffer or client WSI proof.

## Implementation and acceptance order

| Work | Concrete implementation | Acceptance and current state |
| --- | --- | --- |
| GPU/DRM prerequisite inventory | New `Guest/compositor_capabilities.c` queries actual Vulkan device DRM identity, matches the primary character device, queries atomic/syncobj capabilities, timeline feature, sync-file semaphore support and BGRA linear DMA-BUF image features | Actual ARM compile and software/missing-ICD controls pass in [run 37348402397](https://github.com/aghjkshdsj/My-pc/actions/runs/37348402397), source `28e29268…`; actual log receipt independently checked. Not installed in an IPA; no positive phone result. A successful query does not prove allocator/import compatibility |
| Upstream compositor selection | Evaluate pinned wlroots 0.20.2 (`d7835334…`) with Vulkan renderer, DRM backend and a minimal Wayland compositor/client | Official source identity and MIT license inspected. Complete build/license closure and runtime renderer compatibility remain unverified. Do not silently fall back to Pixman/CPU graphics |
| Allocator/import | Supply the actual compatible GBM/DRM allocator and test allocation → Vulkan import → render → external release → native read → Linux fence → reuse | Inspection of the exact published initramfs confirms Vulkan, libdrm and Mesa GBM are already present. Wayland/libseat/libinput/xkbcommon and the compositor closure are now being built separately. Eight Vulkan-exported immutable buffers do not establish compositor-allocated buffer import |
| Changing buffers and clients | Run an actual Wayland surface, compositor render passes and a bounded swapchain, with Linux release synchronization | Verify a minimum three-buffer repeated-use sequence, frame identities and completed readers before overwrite. Exercise client disconnect, window destruction, failed/missing producers/readers, output disable and stop. No CPU deadline authorizes release |
| Input | Native touch/controller/key events → actual Linux input device → compositor seat → client response | Source and end-to-end device tests remain open. A painted cursor or native label is not Linux input proof |
| Display timing | Collect actual presentation feedback/timestamps separately from queue completion and virtual page-flip events | Completion is not physical scanout timing. No FPS target is inferred from eight diagnostic frames or isolated GPU durations |
| SteamOS sessions | Reconstruct/authenticate a coherent Valve ARM rootfs, then its real Plasma/Qt/Wayland and gamescope/Steam/CEF dependencies | Official ARM metadata is inspected; full image has not been reconstructed/authenticated/booted. Keep this separate from the disposable compositor control and do not publish proprietary Valve binaries merely because downloadable |
| Games/performance | Real ARM Steam launch, FEX/Proton game graphics, input/audio/storage/network and measured workloads | Steam under 60 seconds, Hollow Knight 60–80 base rendered FPS at 1280×720, memory, downloads and sustained thermals remain unverified |

The first new inventory does not allocate images, create a logical Vulkan device,
submit GPU work, modeset, or replace either accepted diagnostic payload. It opens
the matching DRM node for capability queries and enables atomic capability only
on its own descriptor. Missing properties are recorded as missing; software or
ambiguous devices and failed Vulkan enumeration cannot become compositor proof.
The hosted workflow compiles this actual ARM program and runs unsuitable-runtime
controls. Those hosted controls are not positive hardware rendering results.

Actual wlroots 0.20.2 sources additionally require Meson ≥1.3, Wayland/server/
scanner ≥1.24.0, protocols ≥1.47, libdrm ≥2.4.129, xkbcommon ≥1.8.0 and Pixman
≥0.46.0 (the renderer subdirectory strengthens the top-level minimum). DRM needs hwdata, libdisplay-info ≥0.2.0 and session support (libudev,
libseat ≥0.2.0); GBM allocator needs GBM ≥21.1. Vulkan build needs loader/headers
≥1.2.182 and glslang. The actual renderer demands external-memory FD, image-format
list, DMA-BUF, foreign queue family, DRM modifier, timeline semaphore and
synchronization2 extensions, then enables timeline/synchronization2 features.
External semaphore FD support is queried separately. The inventory now records
these exact requirements; a Vulkan version number alone cannot satisfy them.
See `evidence/primary/compositor-upstream-requirements.json` for inspected hashes.

Any diagnostic runtime extension must keep exact source/package/header versions,
authenticated dependency checks and corresponding-source/license closure. It
must not mix arbitrary diagnostic libraries into the Valve SteamOS rootfs. The
original host implementation remains MIT; upstream wlroots, Wayland, Mesa,
Linux, QEMU, seat/input libraries and their bundled dependencies retain their
own actual notices and source obligations. Upstream reuse does not reuse an old
VM application or Madeira as the new app base.

Primary API sources checked this date:
[wlroots Vulkan renderer](https://wlroots.pages.freedesktop.org/wlroots/wlr/render/vulkan.h.html)
creates a renderer against a DRM descriptor; the
[DRM backend](https://wlroots.pages.freedesktop.org/wlroots/wlr/backend/drm.h.html)
and [allocator](https://wlroots.pages.freedesktop.org/wlroots/wlr/render/allocator.h.html)
are separate pieces. Khronos specifies
[Vulkan DRM identity](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceDrmPropertiesEXT.html),
[external image-format queries](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceImageFormatProperties2.html)
and [external semaphore queries](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceExternalSemaphoreInfo.html).
These describe interfaces, not compatibility proof for this iPhone or permission
to substitute another desktop architecture.


## Actual upstream compositor build in progress

`tools/build_guest_compositor.py` now builds exact pinned Wayland 1.24.0,
protocols 1.47, libdrm 2.4.129, Pixman 0.46.4, xkbcommon 1.8.0,
libdisplay-info 0.2.0 and wlroots 0.20.2, using the exact existing guest Mesa
GBM/driver artifact. Staged build metadata is relocated while installed guest
paths remain `/usr`; ELF dependency checks and authenticated exact Ubuntu
source-package closure run before publishing an artifact. Full upstream git
source archives, original notices, Mesa corresponding source and build recipes
are retained. Hosted missing-renderer startup must fail before a Wayland session
starts; help/startup controls are not positive compositor graphics proof.

The first build compiled its six dependencies, then correctly rejected the older
Pixman 0.44.2 at the compositor's stricter renderer requirement. That pin is
updated to 0.46.4; a new full build remains pending. This is an ordinary build
repair, not an iOS blocker. Wayland client WSI, seat/device access, allocator
import, actual repeated composition and input remain separate device gates.
The prior Mesa was built with no Wayland WSI platform; successful compositor
compilation alone cannot establish Vulkan Wayland game-client presentation.
