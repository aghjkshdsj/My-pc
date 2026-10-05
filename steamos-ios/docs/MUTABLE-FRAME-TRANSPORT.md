# Moving Linux output: explicit buffer ownership before compositor integration

The current eight-image diagnostic holds every source immutable until shutdown.
The resource-ID deduplication in GuestFrameBudget.h would skip changing contents
of a reused buffer. NativeScanoutABI1 has installation/flush generations and a
borrowed texture, but no per-frame guest identity or native consumer release
acknowledgement. Neither mechanism is a production swapchain.

FrameLeaseLedger.h now implements the bounded ownership table for a future
three-buffer transport. It is independent source code and is not connected to
the shipping ABI1, Metal consumer or Linux compositor. Compilation/rejection/
sanitizer results are source-contract results; no phone animation, transport or
memory-performance result is implied.

Each lease identifies a session, resource, resource incarnation and globally
increasing content frame serial. Repeating a resource ID does not repeat a
frame. The initial layout is validated as linear 1280x720 BGRA8 on one native
device, with actual device alignment supplied by the adapter, bounded stride/
offset/backing size and no arithmetic wrap. Three buffers contain 11,059,200
pixel bytes before driver allocation overhead. The table stores no texture
pointers and uses no allocations. Resource retention remains an adapter duty.

| Transition | Required real observation in the future adapter |
|---|---|
| Free to Producing | Previous exact release acknowledged after guest reacquisition |
| Producing to Ready | Current producer fence complete and external queue ownership released |
| Ready to Consuming | Exact ticket/source/device and bounded native consumer capacity |
| Consuming to ConsumerFinished | Actual terminal native command completion for that ticket |
| Ready or ConsumerFinished to ReleaseSent | No native reader pending; dropped Ready frames have never been submitted |
| ReleaseSent to Free | Exact release token and guest reacquisition acknowledgement |

At most two GPU consumers may be pending. No CPU timeout, background event,
resource reinstallation, successful Vulkan enqueue or display callback can
pretend that a native reader completed. Delayed/duplicate callbacks and stale
sessions/release acknowledgements cannot free a later frame. Background/timeout
quarantines the session and blocks new work, while actual outstanding producer/
consumer completions can drain retained resources. Terminal GPU errors also
quarantine the session. Buffer release and successful presentation are distinct:
the native GPU samples the source into a drawable, so the source may be released
after sampling completes; actual drawable timing is still needed independently.

All table operations must run on the same transport executor. Native Metal
callbacks post their actual completion there. The ledger does not invent an
observation, fence, guest acknowledgement or physical device identity, and does
not certify GPU/phone behavior from Boolean arguments.

The rejection workload covers wrong layout/ownership/device, missing producer
fence, premature reuse, capacity pressure, reversed completions, stale sessions/
incarnations, duplicate completions/releases, incorrect acknowledgements,
background quarantine, GPU failure and draining an already-active producer.
100,000 content frames reuse exactly three resource identities. Address and
undefined-behavior sanitizer runs check the actual implementation. This is a
hosted CPU state-machine workload, not a rendered-frame benchmark.

Next integration steps remain mandatory:

1. Extend the pinned engine with explicit content-ticket and consumer-release
   transport. Carry the exact guest resource/fence identity across native
   completion; retain the original renderer/console cleanup ownership. Review
   command/fence queue lifetime and forbid arbitrary callback-thread access to
   QEMU state. ABI1's diagnostic path remains preserved.
2. Connect guest buffer reacquisition to that release. The pinned source's
   resource flush invokes display update, while renderer fence completion has a
   separate response path. Its present implementation does not expose a native
   release token. A completed renderer fence is not accepted as display-consumer
   release without a traced dependency. Kernel page-flip/out-fence behavior must
   be tested against native completion, not assumed.
3. Render changing Linux Vulkan contents into a fixed pool, sample imported
   textures to the real screen, reuse only after matching release/reacquisition,
   and test interruption/resize/teardown with no steady-state full-image CPU
   readback. Preserve diagnostic endpoint checks separately. Record frame IDs,
   producer/transport/consumer/display timings, queue depth and memory footprint.
4. Add the real Linux WSI/compositor path and then the requested SteamOS desktop
   and Game Mode. A custom moving shader is a transport gate; it cannot satisfy
   Plasma/KWin, gamescope, Steam ARM/CEF or FEX/Proton.

Linux documents [KMS explicit fences and page flips](https://docs.kernel.org/gpu/drm-kms.html):
producer readiness and buffer recycling have separate obligations. These
semantics guide the bridge but do not establish that the existing virtual GPU
already propagates native iPhone release completion. Source reuse stays within
the selected ARM Linux/QEMU/Venus/native Metal architecture. No substitute
Darwin syscall layer, old VM app, native preview or Madeira app is adopted.

Steam<60s, Hollow Knight60–80baseFPS at 720p, sustained pacing/thermals, games,
audio/controllers/downloads/overlays/plugins and the complete desktop/client
remain unfinished. This ledger creates no new percentage or device milestone.

The pinned release20 engine/release17 guest dependency trace is now recorded in
evidence/primary/linux-metal-release-source-trace.json. It identifies the
inherited 500ms forced console-unblock timer and the exported-image guest fence
gap as mandatory integration work. Neither timeout nor renderer enqueue may
free a live native reader. See [next implementation](MOVING-OUTPUT-INTEGRATION.md)
for the component changes and distinct source/device acceptance requirements.
This trace itself changes no upstream code and establishes no moving phone output.
