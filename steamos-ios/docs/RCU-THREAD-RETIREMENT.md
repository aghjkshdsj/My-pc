# QEMU initialization-thread retirement

The fresh host previously called the source-pinned shared-library `qemu_init`
on a `std::thread` and returned after `qemu_cleanup`, lock release and worker
pool retirement. In this QEMU library build, `system/vl.c:qemu_init` calls
`rcu_register_thread`. The host omitted the matching unregister before its
worker exited. Joining the worker does not remove its reader from QEMU's
registry; its thread-local storage can disappear while RCU still references it.

QEMU's [RCU API documentation](https://www.qemu.org/docs/master/devel/rcu.html)
describes registration and unregistration. The
[upstream header](https://github.com/qemu/qemu/blob/master/include/qemu/rcu.h)
requires unregistration before thread exit. The actual UTM-patched QEMU 10.0.12
source input is SHA256
7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a;
the original corresponding-source archives include that input, original UTM
patches, fresh patches and compilation configuration. `util/rcu.c` stores the
thread-local reader in its locked registry and removes it on unregister.

The correction exports the existing upstream `rcu_unregister_thread` definition
in the separate native scanout engine. The host resolves that exact function
before initialization, marks its local lease only after `qemu_init` returns,
and retires the lease on that same thread after cleanup, BQL/replay lock release
and the first autorelease-pool drain. It records the actual returned retirement
before publishing worker completion and joining. Destruction is a fallback for
normal C++ unwinding; signals, process termination and library `exit` are not
converted into successful retirement. A missing export fails before Linux boot.
QEMU global state still permits one initialization per app process.

`QEMUInitThreadLeaseTests.cpp` exercises real native threads and TLS registration
counters, same-thread explicit and destructor retirement, C++ exception unwind,
missing/duplicate/wrong-thread calls and an omitted-retirement negative control.
It does not execute QEMU or establish an iPhone fix. Both optimized and
address/undefined-behavior-sanitized executions are required by the IPA workflow.
The engine build additionally requires shared-library registration mode, a real
external definition and an actual RCU compilation command. Package verification
checks defined external Mach-O symbols, rejecting a private/local/undefined
symbol or a string. Phone receipt validation requires the actual retirement
flag and joined worker, and retains every original graphics/timestamp control.

Build4000025 is a targeted crash-fix candidate. Its engine run37244178261 uses
sourcee31b9fcc6609b8ab50f8d6f72acd7cf9f1124300 and passed its actual engine audit.
The [published package](https://github.com/aghjkshdsj/My-pc/releases/tag/steamos-ios-guest-gpu-gate-20)
passed device-target iOS Release run37245060441 at source
928b1db91b1ee1713e70ddee2c5253ba6676ca93. Optimized/sanitized native tests each
passed 1,001 retirements, and 115 Python controls passed. Eleven public files,
including new engine corresponding source, were independently checked; all
eighteen selected source files match, the actual export is defined, and host
dSYM UUID D7C40BC0-BB7F-331B-AF02-CCD7118B1D92 matches the packaged executable.
IPA SHA256: 1242db7d93eead6a9f3c00b268979b7db24e7c2b20586490a18468297ebae6ed.
These are build/package checks. Original and corrected device results stay
separate in the private local coverage record; a completed owner-observed run
cannot prove all future crashes are eliminated. Readiness to advance is assessed
against that private evidence rather than compilation or elapsed time alone.
Next work is [moving-output integration](MOVING-OUTPUT-INTEGRATION.md), with
explicit native-reader completion, guest buffer reacquisition and lifecycle
ownership. An unchanged diagnostic rerun is not a new transport milestone.

No new engine architecture, renderer or external dependency is substituted.
QEMU TCG remains software system emulation, with the existing native
Venus/virgl/MoltenVK/Metal graphics path. The eight immutable guest frames are
unchanged. QEMU's GPL and all original dependency notices/corresponding source
remain required; the fresh host lease is MIT. Production mutable-buffer
transport, compositor/WSI, SteamOS desktop/Game Mode/ARM Steam, FEX/Proton and
all game/startup/sustained-performance targets remain unfinished.
