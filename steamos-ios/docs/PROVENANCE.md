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
locks and build receipts. ANGLE also has a successful physical-iOS compile
receipt; its runtime loader and remaining graphics dependencies need integration
and device evidence. Older HTTP URLs,
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
physical-phone offscreen check passed in build 4000010. ANGLE compilation is
accepted below; the complete phone guest transport/presentation stack remains
unfinished.


The separate ANGLE build retains the exact reviewed engine/configuration paths,
complete tracked source/license files and the compatibility patch. ANGLE BSD
terms, Apple configuration notices and third-party per-file notices remain in
that source; selecting an engine from WebKit does not reuse a WebKit application.
Public-SDK build settings remove Metal ownership identity and WebCore-only client
restrictions. Actual public-SDK ARM64 iOS compilation, exports and public-framework
imports passed in run 37075043878. This establishes compile acceptance only.
The subsequent explicit framework-rpath dispatch adapter is preserved in both
the generated EGL source and its generator; its revised build passed run 37077105285, with exact source, patches and hashes
retained as a separate compile gate. No application source, runtime acceptance or guest GPU result is implied.

Guest Mesa is independently source-built from the official 26.2.2 release and its
[published checksum](https://docs.mesa3d.org/relnotes/26.2.2.html), using only virgl
and Venus drivers. Its full release source, actual Meson settings and fresh recipe
are retained. Mesa includes per-file licenses beyond its project-level MIT label.
The separate guest userspace archive does not bundle Ubuntu's external dynamic
libraries or ELF loader; their exact package/source versions are recorded for the
subsequent image and license closure. That separate disposable payload now passed
run 37079133580: exact signed Ubuntu package/source versions, source archive
checksums, package copyright files and loader/DSO lookup closure are retained.
It includes glibc 2.39-0ubuntu8.9, libdrm 2.4.125-1ubuntu0.1~24.04.2, Vulkan
loader 1.3.275.0-1build1, expat 2.6.1-2ubuntu0.6, zlib
1:1.3.dfsg-3.1ubuntu2.2 and GCC 14.2.0-4ubuntu2~24.04.1 runtime libraries.
glibc LGPL, GCC runtime exceptions and all remaining per-file/package terms
remain applicable. Real Linux boots exercise this disposable runtime, while
both missing-3D controls reject Vulkan. This closes the diagnostic payload's
runtime/source packaging; it does not authenticate or assemble the SteamOS rootfs.

The EGL-enabled renderer passed run 37078312649 against the revised ANGLE build.
The separate QEMU GPU engine and explicit Darwin ANGLE Metal/GLES 3 adapter passed
physical-iOS compilation in run 37078645613. All original engine archives, exact
libucontext source, adapter patch, recipes and actual build configurations are
preserved alongside the complete GL/Venus/ANGLE source closure. The new app only
packages the required native framework dependency closure and the exact earlier
MoltenVK build. No upstream application is the implementation base. Public
SDK imports exclude IOKit, private Hypervisor and Neptune. Source inspection,
library compilation and negative controls cannot establish a guest shader,
phone Metal completion, presentation or game result.

The build 4000011 phone exit exposed an omitted Pixman dependency of EGL-headless.
Corrected engine run 37092127907 enables the already source-pinned Pixman library,
retains its complete source archive/patch/license notices and verifies the actual
headless compile command and registration export. Pixman's MIT/Xorg per-file
notices remain applicable. The small GPL QEMU adapter preserves the upstream
initializer and adds the registration helper to QEMU's explicit library export
list; its original source, patch and actual build configurations are retained.
Build 4000012 packages ten native frameworks, including Pixman, and passed exact
independent public IPA verification. No new application implementation base or
architecture substitution was introduced. These are build/package checks,
not successful phone graphics or SteamOS/game evidence.


Build 4000013 retains complete original renderer/QEMU source and generated
failure-diagnostic/context-result patches. Actual native renderer run 37095310400
and engine run 37095545014 passed compilation and symbol/configuration audits;
corrected Linux/Mesa runtime run 37095653651 passed hosted boot controls.
Corresponding sources accompany the independently verified prerelease.
Allocation policy, original license obligations and shader acceptance remain
unchanged. Previous build receipts and releases are preserved.

Build 4000014 deliberately changes the renderer's Darwin communication-file
backing when the fresh host provides an explicit app-private directory. The
new independent MIT helper and native tests accompany the complete original
virgl/epoxy/ANGLE source, scoped generated patch and recipes; upstream and
per-file licenses remain applicable to the combined libraries. Actual renderer
run 37176336596 and integrated engine run 37176578369 passed native Darwin
allocator tests and physical ARM64 iOS compilation. Their receipts distinguish
the new allocation policy from the retained failure-only diagnostic patch.
Neither native tests nor compilation establish iOS sandbox execution or Metal
memory import. The corrected Linux/Mesa payload and MoltenVK input are retained;
no previous application implementation or Android runtime is imported.
The public build 4000014 IPA and newly changed fresh/engine source archives were
independently downloaded and hashed. Nested helper, patch, tests and original
renderer/epoxy archives match the shipped engine receipt; fresh host source
matches the public package. Full corresponding source and applicable notices
accompany the prerelease. No Valve client or game content is distributed.

Build 4000015 uses a separately pinned MoltenVK observer compiled in run
37178467526 at source `3f83d181b40439f868fba52abe54f02e9b857c36`.
Original MoltenVK/dependency source and Apache-2.0/per-file notices accompany
the generated queue patch, fresh MIT observer headers, native fixtures and
recipes. Full fresh host source and its MIT license also accompany the release.
The observer registers before the unchanged guest command-buffer commit and
adds no GPU work or result override. The independent public download verified
the actual export, ten-framework import/code closure, exact payloads and source
archive headers/patch/fixtures/original queue. The unchanged QEMU/GL/Venus engine
has separate retained provenance. Earlier native MoltenVK and guest-GPU packages
remain preserved and independently verifiable; the new observer does not inherit
an earlier package's phone acceptance. No Android application base or replacement
Linux architecture is adopted.

The owner-selected DroidDeck archive is pinned and inventoried separately.
[DroidDeck blueprint and license mapping](DROIDDECK-BLUEPRINT.md) distinguishes
GPL-3.0 application code, per-file third-party terms and external source inputs.
No Android application code, assets, binaries or signing inputs were copied into
the fresh host. Implementation reuse would require attribution and compatible
source/license distribution; a functional blueprint does not establish a
completed source closure or phone performance result.


Build 4000016 retains exact engine and Linux payload pins, and distributes the
changed fresh recovery journal, native/Python fixtures and desktop verifier with
its complete fresh source archive. The public archive was independently checked
against the shipped host/test source. It includes no owner phone records. The
native scanout review uses the exact distributed QEMU and renderer source;
source/configuration review does not establish actual image import/presentation
or change upstream licensing obligations.


Build 4000017 adds fresh MIT `Engine/NativeScanoutABI.h`, guest image export/KMS
source, QEMU native scanout patch, ARM64 iOS import consumer, receipt validators,
fixtures and build recipes. The source-built native engine variant is pinned to
6b6e268bffdce59d2d15b319abdee46eaa4b8cee / run 37215070827, with original QEMU,
compiled configuration and narrow patch/header in complete corresponding source.
It retains the same pinned renderer/MoltenVK/ANGLE dependency provenance. The
standalone guest extension retains exact parent kernel/runtime/source, adds only
its init/image diagnostic and includes build headers plus libdrm/Vulkan copyright.
No Android/old-app source or private signing/device material is a fresh input.

The explicit DRM modifier correction is fresh query/creation source against the
same pinned Mesa/Vulkan/libdrm APIs. Guest run 37218376178 at source
7f77b026112b4161964f0f38ca6df700facbe750 passed actual ARM compilation and negative
controls; its corresponding source includes the query contract and native
fixtures. Applicable QEMU/Linux/BusyBox GPL, glibc LGPL, compiler exceptions and
renderer/graphics per-file terms remain unchanged. Fresh MIT files do not remove
combined-distribution obligations. Complete original sources/patches/recipes,
configuration and notices accompany prereleases, without proprietary Valve/game
content. Public package receipt flags distinguish independently downloaded IPA/
fresh source/checksum/verification from large source assets checked only against
CI/release hash metadata. Neither kind of package check certifies phone import,
zero-copy transport, presentation or gameplay.
