#!/usr/bin/env python3
"""Collect the pinned QEMU/dependency source and our build modifications."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tarfile
import urllib.request

pin = '7eadb056ae0f91d979059544d0ddcd2d5a40be92'
folder = pathlib.Path('build/linux-arm/source-materials')
folder.mkdir(parents=True, exist_ok=True)
catalog = urllib.request.urlopen(f'https://raw.githubusercontent.com/utmapp/UTM/{pin}/patches/sources').read().decode()
urls = [re.search(r'^' + key + r'="([^"]+)"', catalog, re.M)[1].replace('http://ftp.gnu.org/', 'https://ftp.gnu.org/')
        for key in ['PKG_CONFIG_SRC', 'FFI_SRC', 'ICONV_SRC', 'GETTEXT_SRC', 'GLIB_SRC', 'PIXMAN_SRC', 'SLIRP_SRC', 'QEMU_SRC']]
urls += [f'https://github.com/utmapp/UTM/archive/{pin}.tar.gz',
         'https://github.com/utmapp/libucontext/archive/9b1d8f01a6e99166f9808c79966abe10786de8b6.tar.gz']
metal = os.environ.get('MYPC_PACKAGE_METAL') == '1'
if metal:
    for name in ('EPOXY', 'VIRGLRENDERER'):
        repo = re.search(r'^' + name + r'_REPO="([^"]+)"', catalog, re.M)[1].removesuffix('.git')
        commit = re.search(r'^' + name + r'_COMMIT="([^"]+)"', catalog, re.M)[1]
        urls.append(f'{repo}/archive/{commit}.tar.gz')
def download(url):
    path = folder / url.rsplit('/', 1)[1]
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, path.open('wb') as output:
        while block := response.read(1024 * 1024):
            digest.update(block)
            output.write(block)
    if path.name == 'qemu-10.0.12-utm.tar.xz' and digest.hexdigest() != '7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a':
        raise ValueError('QEMU source checksum mismatch')
    return {'url': url, 'file': path.name, 'sha256': digest.hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    records = list(pool.map(download, urls))
if metal:
    angle = folder / 'angle-checkout'
    subprocess.run(['git', 'init', str(angle)], check=True)
    subprocess.run(['git', '-C', str(angle), 'fetch', '--depth=1', '--filter=blob:none',
                    'https://github.com/utmapp/WebKit.git', 'ed78ab6e1a37f4f11583a0bd038f22ec91f3ff10'], check=True)
    archive = folder / 'angle-metal-source.tar'
    subprocess.run(['git', '-C', str(angle), 'archive', '--format=tar', '--output=' + str(archive.resolve()),
                    'FETCH_HEAD', 'Source/ThirdParty/ANGLE', 'Configurations', 'Tools/ccache'], check=True)
    records.append({'repository': 'https://github.com/utmapp/WebKit.git',
                    'commit': 'ed78ab6e1a37f4f11583a0bd038f22ec91f3ff10', 'file': archive.name,
                    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
    # Only the reproducible source archive belongs in the release, not .git.
    import shutil
    assert angle.resolve().is_relative_to(folder.resolve()) and angle.name == 'angle-checkout'
    shutil.rmtree(angle)
(folder / 'sources.json').write_text(json.dumps(records, indent=2) + '\n')
paths = ['LICENSE', 'build/linux-arm', 'app/Madeira/LinuxVMBridge.c', 'app/Madeira/LinuxVMBridge.h',
         'docs/STEAM_ARM_PORT.md', '.github/workflows']
if metal:
    paths += ['build/linux-arm-gpu', 'docs/METAL_RELEASE_NOTES.md',
              'app/Madeira/LinuxVMCore.swift', 'app/Madeira/LinuxVMSession.swift', 'app/Madeira/LinuxVMView.swift']
interpreter = pathlib.Path('build/linux-arm-interpreter').is_dir()
if interpreter:
    paths += ['build/linux-arm-interpreter', 'app/Interpreter', 'docs/STEAM_NO_JIT.md',
              'app/Madeira/LinuxVMCore.swift', 'app/Madeira/LinuxVMSession.swift',
              'app/Madeira/LinuxVMView.swift', 'app/Madeira/LinuxRuntimeInstaller.swift',
              'app/Madeira/GameLibraryCore.swift', 'app/Madeira/StoreCore.swift']
subprocess.run(['git', 'archive', '--format=tar', '--output=' + str(folder / 'my-pc-port.tar'), 'HEAD', *paths], check=True)
(folder / 'README.txt').write_text('Corresponding source for the embedded QEMU runtime.\n'
    'The UTM archive includes upstream patches, dependency configuration and licensing.\n'
    'my-pc-port.tar includes our display bridge, adaptation, exact source pins and build scripts.\n'
    'Build on macOS with Xcode: bash build/linux-arm/build-qemu.sh ios\n'
    'Guest Linux package notices and source package names are in its /usr/share/doc and packages.tsv.\n'
    'Valve Steam binaries are downloaded separately by the user and are not in this archive or IPA.\n'
    + ('JIT-free build: bash build/linux-arm-interpreter/build-qemu.sh ios\n' if interpreter else ''))
with tarfile.open('build/linux-arm/LinuxRuntime-Sources.tar.gz', 'w:gz') as archive:
    archive.add(folder, arcname='LinuxRuntime-Sources')
print('Packaged pinned QEMU, dependency sources, upstream patches and My-pc modifications')
