# Upstream engine reuse and licensing

Starting the host from scratch does not remove the need for mature OS, CPU
translation, graphics and compatibility engines. Valve's Steam/CEF client is
proprietary ELF software; its unavailable source cannot be recompiled into an
iOS Mach-O app by changing project settings. Metal is a GPU API, not a Linux ABI
or general CPU execution mechanism.

The initial host-only probe uses Apple system frameworks and new project source.
Linux-gate-2 additionally loads upstream QEMU 10.0.12-utm, GLib 2.83.0, gettext
0.22.5 and iconv 1.16 built for ARM64 iOS, using a new adapter. It retains only
the four required frameworks. The app does not inherit UTM or Madeira UI,
session/storage implementation or prior native-preview code.

The release attaches exact engine source/configs/patches/recipes and source-built
Linux 6.12.111 / BusyBox 1.38.0 source/configs, plus fresh host source. Upstream
notices and license texts remain in those corresponding-source archives; QEMU's
COPYING and the fresh source license accompany the binary. New authored project
source is MIT; that does not replace the combined QEMU-bearing distribution's
applicable GPL obligations or LGPL/per-file dependency requirements.

The StikDebug activation button calls its documented external URL scheme;
the native adapter implements the functional universal breakpoint ABI and one
fixed callback configuration for QEMU's pre-existing region allocation. No
StikDebug/StikJIT framework, helper, pairing data or full JavaScript source is
redistributed. That project's AGPL license is not silently treated as MIT.
Sources reviewed: [StikDebug 3.1.10 URL handler](https://github.com/StikDebug/StikDebug/blob/3.1.10/StikDebug/Views/HomeView.swift),
[universal protocol](https://github.com/StikDebug/StikDebug/blob/3.1.10/StikDebug/Scripts/universal.js),
and [integration guide](https://github.com/StikDebug/StikJIT/blob/main/INTEGRATION.md).

| Input | Reuse / source | License/distribution work before linking/shipping |
|---|---|---|
| Archive glue/overlays | Reference SHA-256 recorded; MaSieS4Fun SteamOS-Ubuntu lineage | Archive declares GPL-2.0; copied/adapted glue needs attribution, license and corresponding source |
| Linux kernel | Generic ARM virt upstream source, not Qualcomm payload | GPL-2.0-only plus per-file terms; exact source/config/patches/build recipe |
| QEMU/iOS port | Upstream QEMU and audited UTM low-level engine port, not UTM/Madeira app UI | GPL-2.0 and per-file dependency terms; publish exact modified corresponding source and recipes; review combined distribution obligations |
| FEX | [FEX-Emu/FEX](https://github.com/FEX-Emu/FEX), Linux frontend/rootfs/thunks | Upstream MIT plus bundled dependencies/rootfs package licenses; pin Steam-provided version separately |
| Gamescope | Valve plus relevant reviewed archive patches | BSD-2-Clause, subproject notices; preserve patch attribution |
| Mesa/virglrenderer/ANGLE | Guest virgl/Venus, Darwin transport, Metal GL backend | Predominantly permissive but per-file/dependency licenses apply; exact licenses/SBOM, no assumption Qualcomm binary provenance covers host |
| MoltenVK | [KhronosGroup/MoltenVK](https://github.com/KhronosGroup/MoltenVK) and evaluated UTM fork | Apache-2.0 and dependencies; license/NOTICE, shader conversion provenance |
| Proton/Wine/DXVK/VKD3D | Actual Linux Proton from Valve's runtime | Mixed per-component terms (Wine/VKD3D LGPL family, DXVK zlib, Proton build glue separately); corresponding source and replacement/relink obligations as applicable |
| Plasma/KDE/Qt/PipeWire/Flatpak/systemd | Official rootfs and compatible external packages | Mixed GPL/LGPL/MIT/etc; preserve package metadata, notices and applicable source/relink material |
| Decky/plugins/Box64/InputPlumber/MangoHud/LSFG | Full external projects plus archive modifications | Read each exact revision's license; archive specifically identifies GPL-3.0-or-later plugins. Do not assume its root GPL-2.0 covers vendor code |
| Valve SteamOS/client | Official update endpoints, legitimate installation/runtime | Proprietary components and Valve trademarks/terms; do not invent redistribution rights. Prefer user-side verified download where allowed; distro open-source portions still have separate source obligations |
| Games / LSFG models | Owner-licensed inputs | No game depots, credentials or separately licensed proprietary model assets bundled without rights |

This is an integration inventory, not a claim that all combined-license questions
are settled. Keep exact component versions and obligations with every
engine-bearing release. Downloading an archive or a public client manifest does
not itself grant distribution rights. Full open-source licenses/notices will be
retained with the exact CPU engine's corresponding source, not replaced by this
table. Future graphics/game dependencies need their own complete notices and
source/relink material as applicable before publication.

Primary revision reviewed: UTM `7eadb056ae0f91d979059544d0ddcd2d5a40be92`
(2026-09-25). Its `patches/sources` pins QEMU `10.0.12-utm`, virglrenderer
`5d26f605f50f8e22002ec6db5fb775e1992d4e96`, ANGLE/WebKit
`ed78ab6e1a37f4f11583a0bd038f22ec91f3ff10`, MoltenVK
`05604465d691118cfd20f53a48ecf1aad9c12f93` and other dependencies.
The CPU engine and its build inputs are pinned in the published recipes and
receipts. MoltenVK and the native Venus renderer now have separate exact source
locks and build receipts; ANGLE and remaining graphics dependencies retain
review-candidate status. Older HTTP URLs,
old dependency versions and runtime assumptions in upstream recipes must be
audited rather than executed blindly. UTM's private/decompiled Hypervisor shim
is not used as evidence of supported iPhone virtualization.

The new **separate MoltenVK iOS build** locks the reviewed engine revision above
and its seven exact ExternalRevisions commits in `tools/prepare_moltenvk.py`.
Its upstream fetch script is narrowed to checks of already fetched commits;
dependency builds are ARM64/iOS 26/unsigned, and the unrelated macOS clean target
is skipped. Engine and dependencies retain their complete tracked source/license
files in separate source archives, along with every modified recipe and workflow.
This is low-level engine reuse, not an upstream application base. It does not
complete the virgl/Venus/ANGLE guest stack or itself establish Metal execution.
The separate physical-phone offscreen result later passed in build 4000010.
MoltenVK's Apache-2.0 license remains separate from dependencies' exact terms.

Current Valve ARM stable manifest is version `1788652215`, matching the archive;
the publicbeta manifest has changed. Preserve the retrieved manifest digests
and choose **steamdeck_stable** for initial reproducibility. Installation and
launch must not silently switch channels. Verify package SHA-256, size, ZIP CRC
and path/symlink safety transactionally; do not propagate the archive's bootstrap
and client-checksum inhibition as package verification.

Primary receipts are timestamped; online `main` documentation may change.
See [Valve stable manifest](https://client-update.steamstatic.com/steam_client_steamdeck_stable_linuxarm64),
[UTM source pins](https://github.com/utmapp/UTM/blob/7eadb056ae0f91d979059544d0ddcd2d5a40be92/patches/sources),
[Darwin Venus shared-memory implementation](https://github.com/utmapp/virglrenderer/blob/5d26f605f50f8e22002ec6db5fb775e1992d4e96/src/venus/vkr_device_memory.c)
and [FEX forwarding documentation](https://wiki.fex-emu.com/index.php/Development:Setting_up_Library_Forwarding).

The fresh native iOS Venus renderer build pins virglrenderer
`5d26f605f50f8e22002ec6db5fb775e1992d4e96` and libepoxy
`bf98587477fe68d07b93319ece7b40a7d0e2eabe`, with the previously verified
Vulkan-Headers source. These are engine sources, not an application implementation
base. MIT and per-file notices are preserved in complete tracked-source archives,
along with the framework-loader patch, cross-build recipe/config and exact receipt.
The host-only generator dependency is PyYAML 6.0.3; it is not an iOS runtime module.
Build 37064765557 produced two ARM64 iOS frameworks using public Metal/Foundation,
without an EGL/GLX backend or Neptune/private Hypervisor. Its successful compile
is not phone import/serialization/graphics evidence. The separate MoltenVK
physical-phone offscreen check passed in build 4000010. ANGLE and the complete
guest transport/presentation stack remain unfinished.
