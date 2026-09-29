#!/usr/bin/env python3
"""Select UTM's ARM64 threaded interpreter after the shared runtime patch."""
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
common = pathlib.Path(__file__).resolve().parents[1] / 'linux-arm/prepare-utm.py'
subprocess.run([sys.executable, str(common), str(root)], check=True)
script = root / 'scripts/build_dependencies.sh'
source = script.read_text()
anchor = '--target-list=aarch64-softmmu --without-default-features'
assert source.count(anchor) == 1, 'Pinned QEMU build invocation changed'
# Same ARM64 interpreter/linker options as UTM's ios-tci build. Keep the
# narrowed target list and apply the interpreter to both iOS and host tests.
flags = ('--enable-tcg-threaded-interpreter --disable-tcg-interpreter '
         '--extra-cflags=-Wno-unused-command-line-argument '
         '--extra-ldflags=-Wl,-no_deduplicate '
         '--extra-ldflags=-Wl,-random_uuid '
         '--extra-ldflags=-Wl,-no_compact_unwind ')
script.write_text(source.replace(anchor, flags + anchor))
print('Selected threaded interpreter: precompiled dispatch, no native JIT backend')
