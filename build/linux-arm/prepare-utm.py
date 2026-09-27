#!/usr/bin/env python3
"""Narrow the pinned UTM dependency build to the ARM64 Linux bring-up backend.

The fetched upstream tree retains its licenses. Fail on source-shape changes;
do not silently patch a different version. GPU dependencies are a later stage.
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
script = root / "scripts/build_dependencies.sh"
source = script.read_text()

def replace_once(old, new):
    global source
    if source.count(old) != 1:
        raise SystemExit(f"Pinned UTM source changed: expected one {old[:80]!r}")
    source = source.replace(old, new, 1)

def function(name, body):
    start = source.index(name + " () {")
    end = source.index("\n}\n", start) + 3
    replace_once(source[start:end], name + " () {\n" + body + "\n}\n")

function("check_env", """    command -v brew
    command -v meson
    command -v xcrun
    command -v msgfmt
    command -v glib-mkenums""")
function("download_all", """    mkdir -p "$BUILD_DIR"
    for src in "$PKG_CONFIG_SRC" "$FFI_SRC" "$ICONV_SRC" "$GETTEXT_SRC" "$GLIB_SRC" "$PIXMAN_SRC" "$SLIRP_SRC" "$QEMU_SRC"; do
        download "$src"
    done
    clone "$LIBUCONTEXT_REPO" "$LIBUCONTEXT_COMMIT"
    echo "7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a  $BUILD_DIR/qemu-10.0.12-utm.tar.xz" | shasum -a 256 -c -""")
function("build_qemu_dependencies", """    build $FFI_SRC
    build $ICONV_SRC
    gl_cv_onwards_func_strchrnul=future build $GETTEXT_SRC --disable-java
    meson_build $GLIB_SRC -Dtests=false -Ddtrace=disabled -Dintrospection=disabled
    build $PIXMAN_SRC --disable-gtk
    meson_darwin_build $SLIRP_SRC
    meson_build $LIBUCONTEXT_REPO -Ddefault_library=static -Dfreestanding=true""")
replace_once('HVF_FLAGS="--enable-hvf-private"', 'HVF_FLAGS="--disable-hvf"')
replace_once('build $QEMU_DIR --cross-prefix="" $QEMU_PLATFORM_BUILD_FLAGS $QEMU_DEBUG_FLAGS',
    '''build $QEMU_SRC --cross-prefix="" $QEMU_PLATFORM_BUILD_FLAGS $QEMU_DEBUG_FLAGS --target-list=aarch64-softmmu --without-default-features --enable-tcg --enable-slirp --enable-pixman --enable-vnc --disable-tools --disable-docs --disable-guest-agent --disable-hvf''')
replace_once("\nbuild_spice_client\nbuild_vulkan_drivers\nbuild_d3d_drivers\n", "\n")
replace_once("\nremove_shared_gst_plugins # another hack...", "")
script.write_text(source)
# Extend QEMU's existing console translation unit with the small display ABI.
# The append happens after extraction and after upstream's own patch is applied.
display = pathlib.Path(__file__).with_name("qemu-display.inc.c").read_text()
injection = '\n    cat >> "$BUILD_DIR/qemu-10.0.12-utm/ui/console.c" <<\'MYPC_DISPLAY_EOF\'\n' + display + '\nMYPC_DISPLAY_EOF\n'
marker = '    clone "$LIBUCONTEXT_REPO" "$LIBUCONTEXT_COMMIT"\n'
if source.count(marker) != 1:
    raise SystemExit("Missing libucontext download anchor")
source = source.replace(marker, marker + injection, 1)
script.write_text(source)
# Prefer HTTPS even for upstream entries that still spell GNU URLs as HTTP.
sources = root / "patches/sources"
sources.write_text(sources.read_text().replace("http://ftp.gnu.org/", "https://ftp.gnu.org/"))
print("Prepared pinned ARM64 QEMU build: TCG JIT, libslirp, virtio, VNC; no HVF/private frameworks")
