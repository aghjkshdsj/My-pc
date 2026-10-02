# Graphics bring-up evidence

The fresh Linux diagnostics are reproducible prerequisites. They do not mark the
phone Linux-to-Metal path complete. The OpenGL diagnostic already passed hosted
ARM pixel checks and explicitly rejected llvmpipe as acceleration. Vulkan now
has a separate render-pass test rather than treating host Metal compute as proof
of a guest graphics pipeline.

`Guest/vk_gate.c`, `vk_gate.vert` and `vk_gate.frag` render a full-screen triangle
into a 1280×720 optimal-tiled RGBA8 image with phase 0, then phase 41. They copy
the result into host-visible memory after explicit layout/access transitions,
wait for completion, invalidate mapped memory and compare every pixel. Readback
is restricted to diagnostic correctness; the eventual steady-state scanout must
avoid full-frame CPU copies. The independent expected channel sum is 1,219,256,320.

The test requests Vulkan 1.1, records the chosen physical device, device extension
list, relevant format/memory flags and a **subset** of features/limits. Portability
devices are enumerated explicitly and `VK_KHR_portability_subset` is enabled when
advertised. A driver version alone cannot establish compositor/Proton support.
The final transport gate must retain a full feature/format query, not infer it
from this small test.

Hosted CI pins its ICD to lavapipe, enables Khronos validation including
synchronization validation, compiles/validates SPIR-V, verifies 1,843,200 pixels,
and requires the same device to be rejected with exit 20 in acceleration mode.
Its artifact retains executable/shaders, hashes, logs and a scoped JSON receipt.
The [first hosted run](https://github.com/aghjkshdsj/My-pc/actions/runs/37035517982)
passed: zero pixel mismatches, correct independent sum, zero validation errors,
empty validation log, and rejection code 20. Its scoped receipt and 161 advertised
extensions are retained in `evidence/primary/hosted-vulkan-diagnostic.json`.
Validation or pixel errors fail the job. A software receipt never becomes phone,
guest transport, Metal, SteamOS or gameplay evidence.

Remaining integration steps:

1. Phone JIT/Linux execution passed in build 4000007. The 32 MiB split-WX cache
   resolved the recorded allocation failure. Build 4000010 subsequently passed
   the native MoltenVK offscreen gate on the actual phone: both 720p images, all
   1,843,200 pixels, zero mismatches and expected checksum on Apple A17 Pro GPU.
   Phone validation layers were disabled. This does not demonstrate Linux graphics.
2. Source-build pinned Darwin virgl/Venus, ANGLE and MoltenVK engines with public
   iOS frameworks. Audit their external-host-memory path, ownership, alignment,
   cache coherency, fences and resource teardown. Reuse engine code under its
   license without adopting any old app or upstream application as our base.
   The independent MoltenVK iOS workflow is now prepared, with exact commits for
   the engine and all seven external dependencies, a source-only archive and
   physical-iOS Mach-O/import/export checks. Audit found an unneeded required
   macOS IOKit import; build 37056046870 passed after removing that iOS target's
   framework link. The physical phone native Vulkan-to-Metal gate passed in
   build 4000010. The new independent Venus iOS workflow narrows the renderer to
   Venus, public Metal/Foundation, same-process threads and pinned epoxy dispatch.
   Its framework loader patch and exact corresponding source are retained.
   Actual native renderer compile/import/serialization remain unverified.
   Hosted run 37056046909 passed actual Venus serialized shader draws through
   the existing external-host/POSIX SHM path under an explicit test override.
   The native Linux fd route failed export. Neither result proves the Darwin
   bridge, virtio guest kernel or Metal. Pinned UTM's
   complete recipe also builds private Hypervisor, Neptune/D3D and macOS-specific
   KosmicKrisp: those calls are not our iOS build plan. Venus/ANGLE need their own
   narrowed recipe and a fresh display adapter before guest integration.
3. Build guest Mesa virgl/Venus with the matching virtio GPU blob/context protocol.
   Run these same GL/Vulkan diagnostics inside the phone guest and correlate
   fresh guest receipts with host Metal command completion and source identities.
4. Present moving guest-origin frames through a fresh Metal display adapter;
   correlate guest/host/present counters, rotation/resize, pacing and zero-copy
   resource lifetime. Offscreen images cannot satisfy this step.
5. Exercise real gamescope, Plasma, Steam/CEF, FEX game GL, and Proton Vulkan
   features individually, then measure the requested Hollow Knight base FPS and
   sustained thermal behavior. No result from steps 1–4 is game FPS.

Primary specification references used for the new diagnostic:
[Vulkan synchronization](https://docs.vulkan.org/spec/latest/chapters/synchronization.html),
[mapped memory](https://docs.vulkan.org/spec/latest/chapters/memory.html),
[validation feature selection](https://docs.vulkan.org/refpages/latest/refpages/source/VkValidationFeaturesEXT.html),
and [portability](https://docs.vulkan.org/guide/latest/portability.html).
These describe API requirements, not successful iPhone execution.
