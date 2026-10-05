# Next implementation: changing Linux images with bounded native buffer reuse

The eight-frame diagnostic retains eight different immutable guest images. It
has established a bounded Linux Vulkan to native Metal screen path. It cannot
establish that the guest can overwrite one of those images while the host is
reading it, or that an ordinary Linux compositor will receive a correct release
fence. The next implementation is a three-buffer moving-output transport within
the current ARM Linux/QEMU/Venus/virgl/MoltenVK/Metal architecture.

The completed build25 device run is assessed in the private local coverage
record. No additional repetition of the unchanged eight-frame gate is a
prerequisite for implementation. A missing actual drawable timestamp remains a
separate unfinished timing check. No crash in one owner-observed run cannot
certify all future lifecycle behavior.

## Pinned-source dependency trace

The trace reads the exact QEMU input inside release20's engine corresponding
source and the exact Linux6.12.111 input inside release17's guest corresponding
source. It reconstructs the selected final QEMU sources by applying the packaged
UTM, GPU and native-scanout patches as data in recipe order, and matches the
scanout files to the archived pre/post patch digests. It does not execute archive
scripts. Input digests, selected file digests, function locations and source-only findings are recorded in
`evidence/primary/linux-metal-release-source-trace.json`.

1. `ui/console.c:dpy_gl_update` brackets the synchronous display callback with
   a GL block. ABI1 supplies a borrowed texture and install/flush generations;
   it supplies no per-content completion or release token.
2. The original tar input's timer force-clears a GL block after 500ms. The
   packaged UTM patch already removes that behavior: the reconstructed final
   `graphic_hw_gl_unblock_timer` warns after 1000ms and does not release it.
   The new transport must preserve that distinction. A timeout must never
   authorize reuse of a buffer that Metal may still read. An unreleased lease
   must be retained/quarantined; warning alone creates no guest release dependency.
3. `virtio_gpu_gl_block` updates `renderer_blocked` and restarts processing on
   unblock. Engine state must be accessed on its owning executor, through a
   bounded completion handoff, rather than from an arbitrary Metal callback.
4. QEMU's virtio resource flush invokes display update, whereas renderer-fence
   response is a separate path. A renderer fence cannot be represented as native
   screen-consumer completion without connecting the dependency.
5. The pinned guest's `virtio_gpu_plane_prepare_fb` allocates its flush fence
   in the dumb-buffer branch. The current exported host3d Vulkan images cannot
   be assumed to gain a Metal release fence through this code. The fenced flush
   branch waits at most 50ms and ignores the wait result as a completion verdict.

These are identified transport integration gaps. They are not an iOS platform
blocker or grounds for silently replacing the requested Linux environment.
Linux's [KMS explicit fencing documentation](https://docs.kernel.org/gpu/drm-kms.html#explicit-fencing-properties)
defines the display interfaces the guest adapter must satisfy; those general
semantics do not certify this existing virtual GPU bridge.

## Component changes and acceptance

| Component | Required implementation | Evidence needed before acceptance |
|---|---|---|
| Linux producer | Reuse three linear 1280x720 BGRA8 allocations; release/reacquire external queue ownership for each changing content frame | Real producer fences, increasing content IDs, fixed resource identities and actual allocation sizes |
| Linux display driver and guest interface | Connect the exact native reader release to guest-visible recycling; preserve KMS/WSI semantics instead of treating a timeout or enqueue as a fence | Delayed native-reader control holds the corresponding guest reuse; errors and missing release fail without overwriting a live image |
| QEMU/native engine | Add explicit content identity and completion handoff, preserve renderer and console cleanup ownership, preserve the warning-only timer without granting reuse | Matching session/resource/incarnation/content/release identities, executor trace, bounded queue and safe teardown |
| iOS Metal consumer | Retain the exact imported texture/backing, submit bounded GPU consumers, post actual terminal completion to the engine executor | Same physical GPU and alias/layout checks; terminal callback for the exact content; no steady full-image CPU readback |
| Presentation | Record actual drawable timestamps independently of source release | Missing/zero timestamps remain failure; command completion and callback CPU clocks do not substitute for display timing |
| Lifecycle | Quarantine on interruption/resize/timeout; retain active sources until real work drains | Reversed/late callbacks, cancellation and resource removal cannot release another frame or use freed resources |

`Engine/FrameLeaseLedger.h` is the already tested bounded ownership contract.
It is not yet connected to these components. Its hosted reuse/sanitizer result
must not become a claim of moving graphics on the phone.

The next device gate should show visibly changing Linux-generated contents while
the same three resource identities are reused across many frames. Endpoint
pixel checks remain diagnostic-only. The gate must include strict joinable
producer/release/reacquisition receipts, bounded pending work and memory, actual
screen completion and display timing, followed by teardown. Its correctness and
measured timing are separate verdicts; a slow passing sequence is not game FPS.
Only a material new transport test should require another IPA installation.

After that transport gate, implement Linux WSI and a real compositor session,
then the requested SteamOS desktop and Game Mode, and then Valve ARM Steam/CEF
with its external runtime dependencies. FEX/Proton, controllers, audio, downloads,
overlays/plugins and sustained game testing remain tracked in COMPONENTS.md.
Steam usable under60s and Hollow Knight60�80 base rendered FPS at720p remain
unverified targets. QEMU TCG is software system emulation; FEX and Proton are
separate translation/compatibility components, not Linux hardware virtualization.

The new implementation remains fresh host source with necessary upstream engine
reuse. Any QEMU/Linux transport patches retain their upstream license obligations
and complete corresponding source in the release. The MIT lease/host code does
not replace those obligations, and no old VM, preview or Madeira app base is used.
