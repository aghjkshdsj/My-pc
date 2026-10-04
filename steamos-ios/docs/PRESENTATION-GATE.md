# Guest image import and moving presentation: next integration gate

This is a pinned source review and implementation contract. It is not a phone
image-import result, presenter implementation or game performance measurement.
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
| QEMU `hw/display/virtio-gpu-virgl.c`, `virgl_scanout_native_blob` | Requests a handle for a guest scanout resource; accepts a Metal texture when configured; installs the texture and a renderer cleanup callback on the console | Versioned host callback/adapter, explicit engine/ABI identity and resource generation |
| QEMU `include/ui/console.h`, `ScanoutTextureNative` / `ScanoutTextureCleanup` | Carries the native handle and its cleanup ownership | Retain the texture while native display work uses it; do not depend on a borrowed pointer after scanout replacement |
| virglrenderer `src/virglrenderer.c`, `virgl_renderer_create_handle_for_scanout` | Can return a retained native vrend texture, or wrap a shared-memory resource through the EGL/Metal path | Actual Venus exported-image blob, format/stride/offset checks and guest/native identity correlation |
| virglrenderer `src/vrend/vrend_metal.m`, `virgl_metal_create_texture_from_shm` | Maps the backing file, makes an MTLBuffer with `newBufferWithBytesNoCopy`, and creates a linear texture over it; the buffer deallocator unmaps the memory | Allocation bounds, exact row pitch, host page alignment, visibility, producer/consumer fences and destruction tests |
| QEMU `ui/egl-headless.c`, `egl_scanout_texture` / `egl_scanout_flush` | Receives a native texture argument but uses the GL backing ID; its flush can read a framebuffer into a CPU surface | A fresh native Metal presentation branch; this headless listener cannot establish native moving presentation |

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

## Concrete implementation sequence

1. Add a separate guest image diagnostic to the current disposable Linux
   payload. Allocate an exportable, linear RGBA8 image; query actual supported
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
