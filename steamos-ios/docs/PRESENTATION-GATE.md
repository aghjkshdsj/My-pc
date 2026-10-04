# Guest image import and moving presentation: implementation and acceptance

The image producer, versioned native engine callback, ARM64 iOS consumer and
strict receipt join are implemented and compiled. Actual phone image import,
a moving presenter and game performance require separate device acceptance.
Device acceptance is maintained separately in the ignored `evidence/device/`
record. The Linux/SteamOS architecture and DroidDeck functional blueprint remain
selected; this gate extends the fresh host's existing Linux graphics transport.

## Existing engine code that should be reused

The exact QEMU engine at `f3587da0d0bb97508fa3170386547b746d2b6324`, run
37176578369, has `CONFIG_METAL`, `CONFIG_EGL` and
`HAVE_VIRGL_RENDERER_NATIVE_SCANOUT` defined in its saved build configuration;
`CONFIG_GBM` is undefined. Its corresponding-source archive is
`d8f98bde17f9741750df83a39cbb54f6f37377ec750499f7e53c63662a8cea85`.
These are build/source facts, not evidence of native scanout on the phone.

| Pinned source boundary | Observed implementation | Fresh integration still required |
|---|---|---|
| QEMU `hw/display/virtio-gpu-virgl.c`, `virgl_scanout_native_blob` | Requests a handle for a guest scanout resource; accepts a Metal texture when configured; installs the texture and a renderer cleanup callback on the console | Versioned callback implemented; actual guest/native identity and device events still need acceptance |
| QEMU `include/ui/console.h`, `ScanoutTextureNative` / `ScanoutTextureCleanup` | Carries the native handle and its cleanup ownership | Retain the texture while native display work uses it; do not depend on a borrowed pointer after scanout replacement |
| virglrenderer `src/virglrenderer.c`, `virgl_renderer_create_handle_for_scanout` | Can return a retained native vrend texture, or wrap a shared-memory resource through the EGL/Metal path | Actual Venus exported-image blob, format/stride/offset checks and guest/native identity correlation |
| virglrenderer `src/vrend/vrend_metal.m`, `virgl_metal_create_texture_from_shm` | Maps the backing file, makes an MTLBuffer with `newBufferWithBytesNoCopy`, and creates a linear texture over it; the buffer deallocator unmaps the memory | Allocation bounds, exact row pitch, host page alignment, visibility, producer/consumer fences and destruction tests |
| QEMU `ui/egl-headless.c`, `egl_scanout_texture` / `egl_scanout_flush` | Receives a native texture argument but uses the GL backing ID; its flush can read a framebuffer into a CPU surface | Native import branch implemented; a paced CAMetalLayer presenter and moving presentation remain required |

The renderer revision is `5d26f605f50f8e22002ec6db5fb775e1992d4e96`.
The private-file allocator is the separately recorded narrow patch. Reusing
these engine interfaces does not reuse a previous app or fork DroidDeck/Madeira.
The [UTM QEMU source](https://github.com/utmapp/qemu) is an upstream engine
dependency. Exact originals, patches and compiled configuration accompany the
current engine release; current branch contents are not substituted for them.

Khronos's [Metal-object extension](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_metal_objects.html)
provides native Metal object import/export in Vulkan implementations layered on
Metal. It is a host API, not a Linux guest's direct Metal capability. The
existing shared-memory scanout route should be tested before adding another
image transport. An ordinary Linux DMA-BUF file descriptor is never relabeled
an IOSurface.

## Implemented image diagnostic and current source correction

Build 4000017 adds the native callback ABI and separate Linux image diagnostic.
The native engine variant at `6b6e268bffdce59d2d15b319abdee46eaa4b8cee`, run
37215070827, reuses the pinned renderer and original console cleanup ownership.
Fresh native install/flush/disable reports carry actual resource ID and generation;
flush bypasses the headless GL/CPU readback branch. The fresh consumer retains each
borrowed texture, verifies the real Metal buffer alias and layout, waits actual GPU
completion and checks two full guest image phases independently. It cannot accept
image import from the preserved offscreen shader check alone.

Pinned Mesa 26.2.2 Venus rejects external DMA-BUF image queries using legacy
tiling. The corrected guest uses explicit DRM-format-modifier tiling with the
linear modifier, a matching creation list, actual returned-modifier checks and
memory-plane-0 layout. It preserves exact pitch/bounds, producer fences, native
resource identity, pixel checks and cleanup. The native ARM Linux query fixtures
and negative boots passed in run 37218376178, source
`7f77b026112b4161964f0f38ca6df700facbe750`. Native image receipt checks increased
from 33 to 37. Source/build checks are not actual phone import acceptance.

The modifier query and creation contract follow Khronos
[query documentation](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceImageDrmFormatModifierInfoEXT.html)
and [creation documentation](https://docs.vulkan.org/refpages/latest/refpages/source/VkImageDrmFormatModifierListCreateInfoEXT.html).
Host layout checks use the actual Metal texture's
[buffer offset](https://developer.apple.com/documentation/metal/mtltexture/bufferoffset),
[row pitch](https://developer.apple.com/documentation/metal/mtltexture/bufferbytesperrow)
and device linear-alignment query. Linux handles are not treated as IOSurfaces.

Steps 1-3 below now have real implementation and compilation; device acceptance
remains independent. Steps 4-6 remain unfinished. The diagnostic performs two
bounded full-image native readbacks and serializes producer completion. This is
not the steady-state zero-copy presenter or a performance benchmark.

## Concrete implementation and remaining sequence

1. Add a separate guest image diagnostic to the current disposable Linux
   payload. Allocate an exportable BGRA8 image with explicit linear DRM modifier and a kernel-supported XRGB primary framebuffer; query actual supported
   external-memory properties, exact image layout, row pitch and offset. Render
   known phases with the existing guest Vulkan shader and wait for the real
   producer fence. Export the image memory through the guest's supported Vulkan
   FD path and import it into the DRM/virtio-GPU framebuffer path. Reject
   unsupported export, modifier, layout, fence or scanout operations explicitly.
   Keep the accepted offscreen test preserved as a separate control.
2. Extend the engine's native scanout boundary with a versioned callback that
   reports resource generation, dimensions, crop, native texture and lifecycle.
   Handle disable/replacement without substituting a host-generated image. Check
   the actual texture's device, format, dimensions and mapped allocation bounds.
   Reject row pitches that would be silently changed by the upstream alignment
   adjustment. A valid shader receipt alone cannot accept an imported image.
3. Verify both guest phases independently through the real imported texture.
   Allow bounded initial GPU readback solely for pixel/alias correctness. Test
   both aliases, release ordering and stale/invalid resources. Record the guest
   producer completion and host consumer completion separately. A successful
   memory mapping or texture constructor cannot pass the pixel/fence gate.
4. Implement a fresh ARM64 iOS Metal presenter using that same texture, an
   explicit producer-to-consumer synchronization boundary and CAMetalLayer.
   Maintain bounded in-flight ownership and backpressure. Keep textures and
   their backing allocations alive until consumer work finishes. Present moving
   guest-generated phases without steady-state full-image CPU readback/copies.
5. Correlate guest frame sequence, scanout generation, producer completion,
   native submission/completion and actual drawable presentation. Measure
   skipped/repeated frames, waits, pacing and memory alongside resize/rotation,
   background/foreground and shutdown behavior. Capture actual presentation
   times using Apple's [drawable presentation callback](https://developer.apple.com/documentation/metal/mtldrawable/addpresentedhandler(_:)).
   Native command completion by itself cannot establish screen presentation.
6. Extend to Vulkan WSI/compositor and guest OpenGL separately, then test actual
   gamescope and Plasma sessions with the coherent SteamOS rootfs. Diagnostic
   pixels and moving patterns never establish Steam/CEF, FEX/Proton, Hollow
   Knight, sustained game FPS or the under-one-minute Steam target.

The first diagnostic may serialize producer fences for correctness. Its cost
must be recorded; that is not acceptance of a serialized production renderer.
The final display path needs bounded asynchronous ownership and measured frame
pacing. Zero-copy is an independently checked property of the imported image
and transport, never inferred from the name of an allocation API.

## Rejection and coverage requirements

Missing native scanout, software renderers, invalid/stale generation, mismatched
device/format, out-of-bounds stride/offset/crop, failed or missing producer and
consumer fences, premature destruction, duplicate callbacks and absent drawable
presentation prevent the respective acceptance. Source fixtures and native build
checks may reject malformed cases, but only device runs can establish GPU import
and presentation. Unavailable native handles are initially an integration failure,
not evidence that all iOS graphics is impossible.

The upstream source review is preserved locally under
`out/presentation-source-audit/`; selected original QEMU source hashes are in
`qemu-source-selection.json`. The full corresponding source remains in the public
engine archive. QEMU's applicable GPL/per-file terms, virglrenderer's MIT/per-file
terms and all dependency notices remain in force. Fresh host source is MIT;
that does not replace upstream licenses or eliminate combined-distribution
obligations. No proprietary Valve client, game or old app source is included.


## Current BGRA/XRGB format gate

Build 4000019 matches Vulkan BGRA8, DRM XRGB8888, virtio BGRX and Metal BGRA8;
RGBA storage is never relabeled. The pinned-kernel CPU-allocation control creates
and releases the framebuffer through the production helper and reproduces the
old unsupported-format errno 2. It cannot prove Venus native image import. ARM
guest run 37222125501 and full iOS package run 37222312731 passed. Native consumers
and both receipt validators now require exact formats and colour ordering.
Two diagnostic GPU readbacks remain bounded; steady-state presentation and
zero-copy transport remain separate acceptance work. See GPU-GATE-4000019.md.


## Immutable diagnostic resources versus display generations

Build 4000020 reserves one GPU readback per distinct immutable diagnostic guest
resource. A display reinstallation can change generation while retaining the same
image. Repeated callbacks are tracked, but unchanged resource reinstallation does
not consume another readback; modified metadata is rejected. Both validators still
require every installation's valid first flush/disable lifecycle and two distinct
phase0/phase41 resources/pixel results. Hosted regression/physical iOS Release and
independent source/IPA checks passed; fresh phone import remains required.

This is restricted to the pinned two-image immutable diagnostic. A steady-state
presenter must handle changing contents, fences and frame IDs for reused buffers,
and cannot skip new frames merely because a resource ID repeats. It must establish
drawable completion and frame pacing without steady-state full-image CPU readback.
No moving presentation/zero-copy/game performance pass is inherited.

## Visible two-image presentation implementation

Build4000021 adds a fresh CAMetalLayer surface and GPU texture-sampling pass.
The two pinned Linux image resources are joined to actual GPU completion and
positive drawable presentation timestamps. One diagnostic consumer may be in
flight; source textures stay retained through both handlers, including timeout
recovery. Surface loss, foreground interruption, geometry change, missing
completion/presentation, stale identities and incorrect viewport fail the gate.

Source and independent/native rejection fixtures are implemented. Actual
physical-iOS Release and 75 native screen / 92 Python checks passed, and the
published IPA/source were independently verified. Actual phone screen
acceptance remains pending. This closes source
work for a two-image screen diagnostic only; continuous animation, moving-frame
ownership/fences, WSI/compositor, pacing and zero-copy remain separate work.
See GPU-GATE-4000021.md. Original engine and licensing mappings above are retained.

## Scheduled Core Animation route and lifecycle observations

Build4000022 replaces command-buffer presentation in this diagnostic with GPU
scheduling followed by main-thread drawable presentation in a Core Animation
transaction. A foreground/surface/geometry check precedes the actual present
call. Cancellation retires only after real GPU completion, exactly once.
Schema2 receipts require actual route/scheduling/main-thread/foreground/enqueue
observations as well as the original positive GPU/display timestamp join.
A later presentedTime query is diagnostic only; it never replaces a zero callback
timestamp. Lifecycle events have bounded count, reason, real clock and state;
interruptions remain sticky and completed sessions stop recording further events.

Physical ARM64 iOS Release, separate adapter compilation, 98 Python and 100
native screen checks passed. All 14 changed files match independently downloaded
fresh source; kernel, initramfs, receipts and ten frameworks are byte-identical
to build4000021. New phone timing acceptance remains pending. The two immutable
images do not accept continuous animation, mutable frame synchronization, frame
pacing, WSI/compositor, desktop/client/gameplay or sustained performance.
See GPU-GATE-4000022.md and the package-only public receipt. Upstream reuse and
licensing mappings, archived implementations and private device records remain
separate and preserved.
