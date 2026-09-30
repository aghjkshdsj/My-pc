#!/usr/bin/env python3
"""Experimental virgl/ANGLE Metal build layered over the verified 2D backend.

No binary from this experiment is used by the IPA release workflow yet.
"""
import pathlib
import shlex
import sys

root = pathlib.Path(sys.argv[1]).resolve()
script = root / 'scripts/build_dependencies.sh'
source = script.read_text()

def replace_once(old, new):
    global source
    if source.count(old) != 1:
        raise SystemExit(f'GPU source anchor changed: {old[:100]}')
    source = source.replace(old, new, 1)

replace_once('    clone "$LIBUCONTEXT_REPO" "$LIBUCONTEXT_COMMIT"\n', '''    clone "$LIBUCONTEXT_REPO" "$LIBUCONTEXT_COMMIT"
    clone "$WEBKIT_REPO" "$WEBKIT_COMMIT" "$WEBKIT_SUBDIRS"
    clone "$EPOXY_REPO" "$EPOXY_COMMIT"
    clone "$VIRGLRENDERER_REPO" "$VIRGLRENDERER_COMMIT"
''')
replace_once('    meson_darwin_build $SLIRP_SRC\n    meson_build $LIBUCONTEXT_REPO -Ddefault_library=static -Dfreestanding=true', '''    meson_darwin_build $SLIRP_SRC
    meson_build $LIBUCONTEXT_REPO -Ddefault_library=static -Dfreestanding=true
    build_angle
    meson_build $EPOXY_REPO -Dtests=false -Dglx=no -Degl=yes
    meson_darwin_build $VIRGLRENDERER_REPO -Dtests=false -Dvtest=false -Dplatforms=egl -Dcheck-gl-errors=true -Dvenus=false -Dneptune=false -Drender-server-mode=thread -Drender-server-worker=thread''')
replace_once('--enable-pixman --enable-vnc', '--enable-pixman --enable-vnc --enable-opengl --enable-virglrenderer')
patch = shlex.quote(str(pathlib.Path(__file__).with_name('patch-qemu.py').resolve()))
replace_once('MYPC_CROSS_PY\n', 'MYPC_CROSS_PY\n    python3 ' + patch + ' "$BUILD_DIR/qemu-10.0.12-utm"\n')
script.write_text(source)
print('Prepared experimental ANGLE/virgl Metal backend; release backend unchanged')
