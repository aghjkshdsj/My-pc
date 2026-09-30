#!/usr/bin/env python3
"""Append a trusted initramfs archive; do not open or replace the user disk.

Format: https://docs.kernel.org/driver-api/early-userspace/buffer-format.html
"""
import gzip
import hashlib
import json
import pathlib
import stat
import sys


def newc(entries):
    archive = bytearray()
    for inode, (name, mode, data) in enumerate(entries + [('TRAILER!!!', 0, b'')], 1):
        name = name.encode() + b'\0'
        values = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
        archive += b'070701' + ''.join(f'{value:08x}' for value in values).encode() + name
        archive += b'\0' * (-len(archive) % 4)
        archive += data
        archive += b'\0' * (-len(archive) % 4)
    return bytes(archive)


def main(guest, order_file=None):
    guest = pathlib.Path(guest)
    source = pathlib.Path('build/linux-arm')
    desktop = (source / 'desktop-session.sh').read_text()
    anchor = 'export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe\n'
    assert desktop.count(anchor) == 1
    choose = '''if grep -qw my_pc_graphics=virgl /proc/cmdline; then
    unset LIBGL_ALWAYS_SOFTWARE GALLIUM_DRIVER
else
    export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
fi
'''
    desktop = desktop.replace(anchor, choose)
    steam = (source / 'steam-session.sh').read_text()
    assert steam.count(anchor) == 1 and steam.count('-cef-disable-gpu ') == 1
    steam = steam.replace(anchor, choose + '''graphics_options=(-cef-disable-gpu)
if grep -qw my_pc_graphics=virgl /proc/cmdline; then graphics_options=(); fi
''').replace('-cef-disable-gpu ', '"${graphics_options[@]}" ')
    payload = {
        'usr/local/bin/my-pc-desktop': desktop.encode(),
        'usr/local/bin/my-pc-steam': steam.encode(),
        'usr/local/lib/my-pc/steam-bin/taskset': (source / 'steam-bin/taskset').read_bytes(),
    }
    checksums = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in payload.items()).encode()
    files = [(f'my-pc-graphics/{name}', stat.S_IFREG | 0o755, data) for name, data in payload.items()]
    controller = {
        'controller/controller.py': pathlib.Path('build/linux-arm-gpu/controller.py').read_bytes(),
        'controller/my-pc-controller.service': pathlib.Path('build/linux-arm-gpu/my-pc-controller.service').read_bytes(),
        'controller/controller-ci.py': pathlib.Path('build/linux-arm-gpu/controller-ci.py').read_bytes(),
    }
    files += [(f'my-pc-graphics/{name}', stat.S_IFREG | 0o644, data) for name, data in controller.items()]
    checksums += ''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in controller.items()).encode()
    diagnostics = pathlib.Path('build/linux-arm-gpu/output/hardware-tests')
    assert diagnostics.is_dir(), 'Build the hardware diagnostic payload before preparing the boot update'
    diagnostic_checksums = []
    for path in sorted(diagnostics.rglob('*')):
        name = 'my-pc-graphics/hardware-tests/' + path.relative_to(diagnostics).as_posix()
        if path.is_symlink():
            files.append((name, stat.S_IFLNK | 0o777, path.readlink().as_posix().encode()))
        elif path.is_file():
            body = path.read_bytes()
            files.append((name, stat.S_IFREG | (path.stat().st_mode & 0o777), body))
            diagnostic_checksums.append(hashlib.sha256(body).hexdigest() + '  ' + name.removeprefix('my-pc-graphics/') + '\n')
    files.append(('my-pc-graphics/hardware-tests/SHA256SUMS', stat.S_IFREG | 0o644,
                  ''.join(diagnostic_checksums).encode()))
    # The source kernel/initrd and Steam's disk remain unchanged. Append the
    # self-contained test payload only to the verified Metal startup update.
    checksums += ''.join(diagnostic_checksums).encode()
    files += [('my-pc-graphics/SHA256SUMS', stat.S_IFREG | 0o644, checksums),
              ('scripts/local-bottom/my-pc-graphics', stat.S_IFREG | 0o755,
               pathlib.Path('build/linux-arm-gpu/graphics-update.sh').read_bytes())]
    # Debian's initramfs sources ORDER instead of globbing new hooks. Preserve
    # its existing order and append our hook after the normal local-bottom work.
    order = pathlib.Path(order_file).read_bytes() if order_file else b''
    assert b'my-pc-graphics' not in order
    files.append(('scripts/local-bottom/ORDER', stat.S_IFREG | 0o644,
                  order + b'\n/scripts/local-bottom/my-pc-graphics "$@"\n'))
    directories = set()
    for name, _, _ in files:
        parent = pathlib.PurePosixPath(name).parent
        while str(parent) != '.':
            directories.add(str(parent)); parent = parent.parent
    entries = [(name, stat.S_IFDIR | 0o755, b'') for name in sorted(directories, key=lambda x: (x.count('/'), x))] + files
    original = (guest / 'initrd.img').read_bytes()
    overlay = gzip.compress(newc(entries), mtime=0)
    updated = original + overlay
    (guest / 'graphics-initrd.img').write_bytes(updated)
    manifest = {'schema': 1, 'backend': 'virgl-metal',
                'kernelSHA256': hashlib.sha256((guest / 'Image').read_bytes()).hexdigest(),
                'initrdSHA256': hashlib.sha256(updated).hexdigest(), 'initrdBytes': len(updated),
                'launcherSHA256': {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}}
    (guest / 'graphics.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Prepared checksum-verified Metal boot update; rootfs.raw was not opened')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
