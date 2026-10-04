# Build 4000012: Linux works; guest Vulkan shared-resource creation fails

This is the preserved analysis of the build 4000012 failure. Subsequent raw
reports and detailed matching analysis remain local. The current test is
[build 4000014](GPU-GATE-4000014.md), an independently verified prerelease that
uses app-private renderer communication files and retains build 4000013's
corrected DRM bind and native failure diagnostics. The new file adapter passed
native Darwin tests and physical iOS compilation; phone guest graphics remains
unverified. Earlier saved logs have already been received; no repeated export
of the old attempt is needed.

The owner's fresh `linux_gpu` report matches app source
`aa2f8ccfb15eb53a96f70775be8e83ca0c5703b2`, the independently verified build
4000012 IPA, its complete guest/engine metadata and all ten signing-compatible
engine code sections. Device identity is iPhone16,2 / iOS 27.0.1 / build 24A446.
The cached standalone JIT entry is not counted as a newly executed test.
Raw phone documents, nonce, signing data and analysis remain private.

Linux 6.12.111/aarch64/4 KiB pages passes signals, mmap/protection,
pthread/TLS/futex, fork/exec and checksum. The virtio-GPU driver advertises
3D/blob/host-visible/context-init support and capsets 1, 2 and 4 (Venus).
Its 1280×720 allocation/map/CPU-pattern test checks 3,686,400 bytes with zero
mismatches, completes the transfer ioctl and closes the resource. This is
guest memory/driver evidence; independent host pixels and shaders are not proved.

The observed failure sequence decodes as follows. The numerical definitions
were checked against both the exact packaged QEMU standard header and the
[Linux 6.12 virtio-GPU ABI](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/virtio_gpu.h).

| Guest command | Error response | Meaning |
|---|---|---|
| 0x10c RESOURCE_CREATE_BLOB | 0x1200 ERR_UNSPEC | Shared resource was not created successfully |
| 0x208 RESOURCE_MAP_BLOB | 0x1203 ERR_INVALID_RESOURCE_ID | Requested resource is absent |
| 0x209 RESOURCE_UNMAP_BLOB | 0x1203 ERR_INVALID_RESOURCE_ID | Cleanup refers to the absent resource |
| 0x102 RESOURCE_UNREF | 0x1203 ERR_INVALID_RESOURCE_ID | Cleanup refers to the absent resource |

`vkCreateInstance` returns -1, the guest Vulkan test exits 3, and no shader/pixel
receipt is produced. QEMU completes with exit 0 and Linux powers down. This is
a normally completed failed graphics diagnostic; the report does not establish
another native app crash. The existing positive Vulkan validator rejects it.
The partial result is recorded in
`evidence/primary/ios-guest-vulkan-4000012-partial.json`.

## Exact engine and guest source review

The preserved corresponding-source archive for the original graphics engine
retains the same unchanged renderer input used by build 4000012:
virglrenderer `5d26f605f50f8e22002ec6db5fb775e1992d4e96`.
Its nested tracked-source TAR is 17,909,760 bytes with SHA-256
`64894d65871603793b696bc7f21b0d17375007fb26e7a47028cf7252fa7d5f3c`,
checked against its build receipt before review. The changed QEMU headless
registration/Pixman configuration does not modify these blob paths.

Mesa 26.2.2 `src/virtio/vulkan/vn_renderer_virtgpu.c` initializes communication
storage as HOST3D blobs with blob ID 0 and the mappable flag. The reviewed
[renderer context implementation](https://github.com/utmapp/virglrenderer/blob/5d26f605f50f8e22002ec6db5fb775e1992d4e96/src/venus/vkr_context.c)
routes that combination to an anonymous file, host-page-aligned shared mmap,
and resource-table insertion. The
[Darwin allocator](https://github.com/utmapp/virglrenderer/blob/5d26f605f50f8e22002ec6db5fb775e1992d4e96/src/mesa/util/anon_file.c)
uses named POSIX shared memory, optionally with APP_SANDBOX_GROUP_ID; it does
not automatically fall back to an app-private temporary file. That branch's
sandbox behavior is a possible cause, not an observed denial in this report.

QEMU `hw/display/virtio-gpu-virgl.c::virgl_cmd_resource_create_blob` can return
ERR_UNSPEC for guest backing setup, renderer creation or subsequent resource
information lookup. Renderer creation itself can fail at context lookup,
anonymous-file allocation, shared mapping or allocation of tracking objects.
The guest response does not distinguish those branches. Its Vulkan -1 result
does not establish that the phone ran out of physical RAM, that MoltenVK failed
to render, or that the iOS platform fundamentally blocks the requested path.
No such blocker is declared, and no substitute architecture is adopted.

## Historical follow-up and current required evidence

The matched recovery export provides the host output from the existing attempt.
Its Vulkan resource error sequence does not distinguish the exact allocation
branch. Source review also establishes that the preliminary texture request's
bind 0 is incompatible with its non-buffer target; build 4000013 uses render-
target bind 2. CPU-mapped guest pixels cannot independently prove the host
accepted that resource. This source correction is separate from the unresolved
Venus blob failure.

Build 4000013 passed actual native compilation, capture and package checks.
The next fresh JIT-enabled phone attempt uses build 4000014. Its normal report
includes host private-file/context/blob diagnostics and the Linux serial;
reopen-and-share recovery remains available if interrupted. Directory preparation
or a file-open marker cannot establish guest pixels or GPU memory import.
Do not relax shader, non-software-device, completion or pixel acceptance.

Independent Metal completion/import, guest Vulkan shaders, moving presentation,
SteamOS/Steam/FEX and game performance remain unfinished.
