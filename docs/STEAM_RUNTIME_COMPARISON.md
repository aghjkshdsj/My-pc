# Runtime comparison: supplied SteamOS SM8550 and BoxedVN archives

Reviewed 30 September 2026 from the owner's local ZIPs. These observations
describe source architecture, not a benchmark on the owner's iPhone.

| Component | SteamOS-ARM-SM8550 | My-pc ARM Steam preview | BoxedVN FEX64 branch |
|---|---|---|---|
| Host/runtime | Boots Linux directly through ROCKNIX ABL on Snapdragon handhelds | Linux kernel inside QEMU TCG on iOS | iOS app with Boxedwine's userspace Linux syscall implementation |
| CPU path | ARM Steam runs on the real ARM CPU; FEX translates x86 games | ARM Linux instructions still pass through QEMU; x86 tests add FEX inside Linux | Translated x86 Windows/Wine workloads avoid a whole ARM system VM; native ARM Linux Steam is not this backend's target |
| GPU path | Qualcomm Adreno kernel driver and Turnip/Vulkan with gamescope | Mesa virgl to ANGLE/Metal; current tests exercise GL/GLES | Native host presentation with Vulkan/MoltenVK and D3D/Wine bridges; workload-specific limitations remain |
| Controller | InputPlumber creates a Deck-compatible virtual Linux device | iOS GameController to local virtio-serial/uinput, Xbox-style gamepad | Host controls feed the Boxedwine/Wine environment |
| Immediate reuse | Virtual Linux gamepad concept, controller UI, coherent graphics packages, isolated FEX tools | Keeps the working full ARM Steam login and existing Steam disk | Reference for direct syscall/graphics bridge design and diagnostics |

## What makes the SM8550 project potentially faster

The README, `make-steamos-sm8550.sh`, build/fix notes, gamescope session and
Mesa installer describe a bootable SteamOS image. This is not an Android APK
running a PC emulator. It reconstructs Valve's ARM userspace and combines it
with an SM8550 kernel, Adreno-specific Mesa binaries and gamescope. Native
ARM execution and direct hardware graphics access remove overhead that
changing My-pc's Linux distribution would not remove.

The supplied project does not contain an Apple GPU driver, iOS kernel port,
or the official SteamOS root filesystem. Its Turnip driver, Qualcomm power
controls, bootloader and device trees cannot drive an iPhone's Apple GPU.
Installing those binaries into this guest would not replace virgl with direct
Metal access. Its gamescope/Vulkan path also needs a real guest Vulkan route;
the existing GLES shader gate is not sufficient to validate it.

The controller design is applicable: expose a real virtual Linux gamepad rather
than translate the controller solely into keystrokes. My-pc implements that
idea with its own small fixed protocol and uinput bridge. No third-party
project source was copied from the archives into the release.

## What BoxedVN suggests

The branch includes a real FEX64 adapter, syscall/memory/signal bridges and
native graphics presentation. `README_IOS.md` and the older limitations page
describe early 32-bit builds; the newer `PROGRESS.md`, FEX64 handoff and desktop
launch plan must be read alongside them. The desktop plan explains that its
fixed identity-mapping windows permit one translated process at a time, with
other desktop processes using an interpreter. Its newer progress entries also
describe interpreter-heavy Chromium/V8 workloads and unfinished device
acceptance checks. Those are material limitations for a multiprocess Steam
client. The README's upstream desktop benchmark numbers are not evidence of
this branch's Steam performance on an iPhone.

A userspace syscall bridge could eventually remove QEMU's ARM CPU cost, but
porting this approach to the ARM Linux Steam client requires an ARM ELF loader,
Linux-to-Darwin syscall and signal implementation, memory/threading semantics,
CEF multiprocess support and compatible graphics IPC. Swapping a FEX64/Wine
binary does not provide that runtime. Keep the working ARM Steam path while
collecting measured native-iOS/guest-ARM/FEX results to identify the phone's
current bottleneck.

No claim is made that either supplied project has been run or benchmarked here.
