#!/usr/bin/env python3
"""Temporary account-free CI overlay: fixed VT/serial access flags only."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import pathlib
import stat


def records(data):
    offset = 0
    result = {}
    while offset < len(data):
        assert data[offset:offset+6] == b'070701'
        fields = [int(data[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        offset += 110
        name = data[offset:offset+fields[11]-1].decode()
        offset = (offset+fields[11]+3)//4*4
        body = data[offset:offset+fields[6]]
        offset = (offset+fields[6]+3)//4*4
        if name == 'TRAILER!!!': break
        result[name] = body
    return result


WATCH = '''
def startup_flags():
    import json, pwd, stat
    account = pwd.getpwnam('steam')
    groups = os.getgrouplist('steam',account.pw_gid)
    for _ in range(8):
        time.sleep(10)
        flags = {}
        try:
            node = os.stat('/dev/ttyAMA0')
            mode = stat.S_IMODE(node.st_mode)
            allowed = bool(mode & (0o200 if node.st_uid==account.pw_uid else
                0o020 if node.st_gid in groups else 0o002))
            flags.update(serial_steam_write_allowed=allowed,
                serial_owned_by_steam=node.st_uid==account.pw_uid,
                serial_group_is_steam_group=node.st_gid in groups)
        except OSError: flags['serial_node_missing']=True
        try: text=pathlib.Path('/dev/vcs1').read_bytes().decode(errors='replace').lower()
        except OSError: text=''
        patterns = {'vt_permission_error':'permission denied',
            'vt_serial_open_error':'cannot create /dev/ttyama0',
            'vt_x_server_error':'fatal server error',
            'vt_no_space':'no space left',
            'vt_missing_command':'not found',
            'vt_resource_error':'resource temporarily unavailable'}
        flags.update({key:pattern in text for key,pattern in patterns.items()})
        # Read a private console internally; export only fixed booleans.
        # Never export text, names, paths, profiles or unknown error strings.
        try:
            fd=os.open('/dev/ttyAMA0',os.O_WRONLY|os.O_NONBLOCK|os.O_NOCTTY)
            try: os.write(fd,('MYPC_STARTUP_ACCESS '+json.dumps(flags,sort_keys=True)+'\\n').encode())
            finally: os.close(fd)
        except OSError: pass

'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('guest',type=pathlib.Path)
    parser.add_argument('--journal',action='store_true')
    args = parser.parse_args()
    guest = args.guest
    archive = (guest/'graphics-initrd.img').read_bytes()
    original_bytes = (guest/'initrd.img').stat().st_size
    files = records(gzip.decompress(archive[original_bytes:]))
    controller_name = 'my-pc-graphics/controller/controller.py'
    controller = files[controller_name].decode()
    anchor = "    print('MYPC_CONTROLLER_READY=1', flush=True)\n"
    assert controller.count(anchor)==1
    controller = controller.replace(anchor,anchor+"    import threading\n    threading.Thread(target=startup_flags,daemon=True).start()\n")
    anchor = "if __name__ == '__main__': main()"
    assert controller.count(anchor)==1
    controller = controller.replace(anchor,WATCH+anchor)
    replacements = {controller_name:controller.encode()}
    if args.journal:
        name = 'my-pc-graphics/controller/my-pc-controller.service'
        unit = files[name].decode()
        assert 'StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyAMA0\n' in unit
        replacements[name] = unit.replace('StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyAMA0\n',
            'StandardOutput=journal\nStandardError=journal\n').encode()
    checksums_name = 'my-pc-graphics/SHA256SUMS'
    checksums = files[checksums_name].decode().splitlines()
    for name,body in replacements.items():
        target = name.removeprefix('my-pc-graphics/')
        matches = [i for i,line in enumerate(checksums) if line.endswith('  '+target)]
        assert len(matches)==1
        checksums[matches[0]] = hashlib.sha256(body).hexdigest()+'  '+target
    replacements[checksums_name] = ('\n'.join(checksums)+'\n').encode()
    spec = importlib.util.spec_from_file_location('update',pathlib.Path('build/linux-arm-gpu/prepare-boot-update.py'))
    update = importlib.util.module_from_spec(spec); spec.loader.exec_module(update)
    entries = [(name,stat.S_IFREG|0o644,body) for name,body in replacements.items()]
    archive += gzip.compress(update.newc(entries),mtime=0)
    (guest/'graphics-initrd.img').write_bytes(archive)
    manifest = json.loads((guest/'graphics.json').read_text())
    manifest.update(initrdSHA256=hashlib.sha256(archive).hexdigest(),initrdBytes=len(archive))
    (guest/'graphics.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('MYPC_ISOLATED_STARTUP_PROBE_PREPARED=1')


if __name__=='__main__': main()
