# Performance budget and device procedure

The owner-selected [DroidDeck blueprint](DROIDDECK-BLUEPRINT.md) adds concrete
reference designs for fast-path correctness, metadata caching, resumable downloads,
buffer/fence ownership and display pacing. Its Android startup/microbenchmark
figures are reference measurements on a different platform, not achieved iPhone
results. GPU clock pinning and Android sysfs controls are not carried into iOS.
Base game renders remain separate from optional frame generation.

Build 4000014's renderer communication adapter uses immediately unlinked
app-private regular files. Native Darwin correctness tests passed at 256 bytes,
16 KiB, one 720p buffer size and 16 MiB; this is not a speed or memory-budget
measurement. On the phone, measure allocation latency, dirty/physical footprint,
storage activity, memory pressure and sustained throughput against the actual
working path. File-backed shared mappings must not be described as zero-copy
GPU image import or as a proven performance improvement.

The table below contains **budgets and hypotheses**, not achieved targets. Target device:
owner-confirmed iPhone 15 Pro Max / iOS 27.0.1, with iLoader and StikDebug.

Measured CPU bring-up baseline, build 4000007: owner-supplied iPhone16,2 / iOS
27.0.1 build 24A446 evidence passed exact IPA/source/payload/serial consistency.
Linux 6.12.111 boot plus all four ABI checks completed in **691.06 ms**, with
guest checksum workload wall 4.031 ms and thread CPU 3.716 ms. Configuration:
software QEMU TCG, 2 guest vCPUs, 512 MiB RAM, 32 MiB split-WX cache; guest pages
4 KiB on a 16 KiB host. The app's reported physical footprint after the gate
was 139,348,024 bytes, a point-in-time reading rather than a peak or memory limit.
Thermal state was Fair; no 20-minute sustained test was performed. A single tiny
kernel/checksum run is not SteamOS/Steam launch timing, FEX overhead, game FPS
or a guarantee of sustained performance. Raw reports remain private.

Build 4000009 native Vulkan attempt: engine executable code matched provenance,
MoltenVK loaded, and the native adapter returned exit 0 in **562.53 ms**. Its
GPU/pixel diagnostic was empty, so this run is **incomplete graphics evidence**.
The interval includes native Vulkan setup, two offscreen draws, readback and
teardown; it is not a per-frame GPU measurement and cannot be converted into
game FPS. The reported app footprint afterward was 90,212,072 bytes and thermal
state Nominal, both point-in-time observations without peak or sustained data.
Build 4000010 saves a dedicated structured draw receipt to resolve that gap;
its compiled package and hosted regression passed. The later build 4000010 phone
receipt passed native Vulkan-to-Metal correctness: two 720p images, 1,843,200
pixels, zero mismatches and checksum 1,219,256,320 on Apple A17 Pro GPU. Its
complete setup/draw/readback/teardown took 497.20 ms, not steady-state frame time
or game FPS. Footprint afterward was 90,097,360 bytes and thermal state Nominal.
Validation layers were disabled. No peak-memory or sustained thermal conclusion
is drawn from this one run.

| Path | Initial budget / experiment | Evidence required |
|---|---|---|
| Steam cold launch | <60 s external icon tap to responsive actual ARM client/library; planning allowance 5 s host, 15 s kernel/services, 30 s client/CEF, 10 s network margin | Cooled phone, 3 trials; first-time rootfs/client install and warm launch separate |
| Game CPU | At 60–80 FPS total frame interval is 16.67–12.5 ms. Allocate ~7 ms game CPU + FEX, ≤2 ms OS/transport CPU as initial working budget | Actual Hollow Knight thread/guest/host traces; TCG overhead separately, overlapping GPU work not double-counted |
| Game GPU | Initial ≤5 ms base render + ≤1 ms composition and ≤1 ms submission/transport budget | GPU timestamps/trace, guest-origin frame counter and presents; overlapping stages measured |
| Frame pacing | 60 FPS median ≤16.67 ms, 80 FPS median ≤12.5 ms; report p95/p99 and 1% lows rather than claim average alone | Uncapped/base workload, VSync/cap recorded, no generated frames in base counter |
| Memory | Probe actual app footprint/jetsam; test 1.5/2/3 GiB guest sizes only after measured app limits, never assume all physical RAM is available | Steam/CEF/FEX/game RSS and host footprint, allocation failure, swap and sustained thermal trace |
| Storage | Sparse raw image baseline; compare raw/qcow2 read/write/amplification and queue depths; preserve flush correctness | Cold/warm cache separated, MiB/s, fsync latency, iowait, decompression CPU and block queue occupancy |
| Downloads | Measure network bytes separately from compressed depot bytes and installed bytes, time hash/decompress/write; bounded parallelism/backpressure | Same real depot and network; retry/cancel/resume/integrity, no unverified throughput claims |
| Thermals | 20-minute gameplay, 1-second samples, cooled repeat; record charger/case/brightness/room temperature | thermal state, footprint, FPS/frame-time trend, stalls and host/guest utilization |

The old six-core preview-33 reference report recorded Hot thermal state,
2 GiB guest RAM, ARM one-worker 2.601 ms, FEX one-worker 3.763 ms and FEX launch
around 2.03 s. Its short ARM/FEX virgl diagnostic reported 277/187 render FPS.
Those small synthetic scenes do not predict game FPS. Prior reported Steam
installation was ~10 minutes and launch ~3 minutes. Two-core and six-core runs
were not controlled for heat/background CEF load; do not declare an optimal CPU
count from those runs. User data and working previews remain untouched.

The previous Metal path read full guest frames back to CPU, converted RGBA/BGRA
and coalesced updates at ~30 Hz. At 720p, a BGRA frame is 3,686,400 bytes; 80
frames/s means 294,912,000 bytes/s **per full-frame transfer**, before extra copies
and GPU synchronization. A high offscreen render counter can coexist with slow
presentation. The new target is guest GPU resources -> shared native resources
-> Metal presentation, with GPU fences and bounded buffering, avoiding full-frame
CPU readback except verification samples. This is an engineering target.

Avoid giant eager virtual-address reservations and allocator rewrites: previous
Dokimon evidence showed a stripped-relocation x64 executable failed before game
code when its fixed base was rejected. That is a regression lesson, not a ported
fix or proof that Linux FEX behaves identically. Separate app UI optimization
from validated engine memory/signal behavior. Native library UI appearance in
94 ms excluded pre-main/icon tap and was not SteamOS startup.

Hollow Knight test: record Steam app/depot/build ID, Linux x64 versus Windows
Proton path, Unity renderer, scene, graphics settings, 1280×720, VSync/frame cap,
controller, Low Power Mode, battery/charger and thermal state. Count original
game renders, guest compositor outputs and host presents separately. Record
launch/sign-in/download failures as failures. Never label a shader demo or a
generated-frame count as Hollow Knight base FPS.

Build 4000012's fresh phone guest-GPU attempt completed in 1156.26 ms with
Linux ABI and DRM allocation/map/pattern/transfer-ioctl success, followed by
failed Vulkan initialization and orderly poweroff. Its checksum workload took
5.357 ms CPU / 5.596 ms wall; the DRM memory check took 33.847 ms. None is a
GPU frame-time, Steam startup or gameplay measurement. The after-test app
footprint was 275,466,320 bytes, a single point rather than a peak; thermal
state was Nominal before and after, without sustained sampling. The failed
shared-resource/Vulkan initialization is not proof that physical RAM was
exhausted. Full game CPU/GPU, frame pacing and sustained thermal targets remain
unverified.
